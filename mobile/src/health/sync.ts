import AsyncStorage from "@react-native-async-storage/async-storage";

import {
  MAX_ENTRIES_PER_SYNC,
  activityApi,
  isSyncableEntry,
  type DeviceActivityEntry,
  type DeviceActivitySource,
} from "../api/activity";
import { ApiError } from "../api/client";
import type { HealthProvider } from "./provider";

const WATERMARK_STORAGE_PREFIX = "fitora.health.lastSync.v1";
const SEEN_IDS_STORAGE_PREFIX = "fitora.health.seenIds.v1";

/**
 * How many of the last sync's ids to remember for the stability check below.
 *
 * Enough to cover any realistic overlap day. If a sync sends more than this,
 * the remembered set is incomplete and the check is skipped rather than
 * guessed at — a false accusation of a broken provider would be worse than
 * no check.
 */
const SEEN_IDS_CAP = 500;

/**
 * How far back the very first sync reaches.
 *
 * Not "everything": a lifetime of HealthKit history is a large, slow import
 * of data the user probably doesn't expect to appear, and the charts only
 * look back 90 days anyway.
 */
export const INITIAL_HISTORY_DAYS = 30;

/**
 * How far before the watermark each later sync re-reads.
 *
 * Devices finalise a workout's distance and calorie figures minutes to hours
 * after it ends, and a phone that was out of range backfills once it syncs
 * with a watch. Re-reading a day of already-seen records costs one request
 * and is free of consequence, because the server matches on `external_id` and
 * updates in place.
 */
export const OVERLAP_DAYS = 1;

export type HealthSyncOutcome =
  /** The user hasn't granted `wearable_access`; nothing was read or sent. */
  | { kind: "consent_required" }
  /** The OS refused, or the user declined the system dialog. */
  | { kind: "permission_denied" }
  | {
      kind: "synced";
      /** Records the device offered, before filtering. */
      read: number;
      /** Records the server refused to be sent, because they were impossible. */
      dropped: number;
      /**
       * Records dropped because another record in the same read already used
       * their `external_id`. A provider whose ids collide would otherwise
       * have one activity silently overwrite another, server-side.
       */
      duplicateIds: number;
      created: number;
      updated: number;
      /**
       * The overlap re-read returned records from days the last sync already
       * covered, and not one of them carried an id we sent before.
       *
       * That means the provider is minting a new id each time it is asked
       * about the same record — the one contract `HealthProvider` cannot
       * enforce (see `docs/health-integrations.md`). Left unnoticed it
       * duplicates the user's history a little more on every sync.
       */
      unstableIds: boolean;
    }
  | { kind: "failed"; message: string; /** Pages that did land before the failure. */ partial: boolean };

function watermarkKey(source: DeviceActivitySource): string {
  return `${WATERMARK_STORAGE_PREFIX}.${source}`;
}

function daysBefore(date: Date, days: number): Date {
  return new Date(date.getTime() - days * 24 * 60 * 60 * 1000);
}

function seenIdsKey(source: DeviceActivitySource): string {
  return `${SEEN_IDS_STORAGE_PREFIX}.${source}`;
}

/** Ids sent by the previous sync, or null when there is nothing usable. */
interface SeenIds {
  ids: string[];
  /** The last sync sent more than the cap, so `ids` is only part of it. */
  truncated: boolean;
}

/**
 * Drop records that reuse an `external_id` already used earlier in the same
 * read.
 *
 * The server keys on `(user_id, source, external_id)`, so sending a collided
 * pair means the second silently overwrites the first and the user loses an
 * activity they really did. Keeping the first and reporting the rest turns a
 * silent loss into a visible number.
 */
function dedupeById<T extends { external_id: string }>(
  entries: T[]
): { unique: T[]; duplicates: number } {
  const seen = new Set<string>();
  const unique: T[] = [];
  for (const entry of entries) {
    if (seen.has(entry.external_id)) continue;
    seen.add(entry.external_id);
    unique.push(entry);
  }
  return { unique, duplicates: entries.length - unique.length };
}

/**
 * Whether the provider appears to be minting a fresh id for a record it has
 * already reported.
 *
 * Only the days the previous sync definitely covered are examined — records
 * dated strictly before the last sync ran. Those were seen before, so at
 * least one of their ids should be familiar. Records from the sync day itself
 * are excluded: an activity logged an hour after the last sync is genuinely
 * new, and counting it would accuse a correct provider.
 *
 * Silent when there is nothing to compare against: the first sync, an
 * overlap window the user left empty, or a remembered set that was truncated.
 */
function idsLookUnstable(
  entries: { external_id: string; logged_at: string }[],
  watermark: Date | null,
  previous: SeenIds | null
): boolean {
  if (watermark === null || previous === null || previous.truncated) return false;
  if (previous.ids.length === 0) return false;

  // Both sides are ISO calendar dates, so a string comparison orders them.
  const watermarkDate = watermark.toISOString().slice(0, 10);
  const settled = entries.filter((entry) => entry.logged_at < watermarkDate);
  if (settled.length === 0) return false;

  const known = new Set(previous.ids);
  return !settled.some((entry) => known.has(entry.external_id));
}

function chunk<T>(items: T[], size: number): T[][] {
  const pages: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    pages.push(items.slice(i, i + size));
  }
  return pages;
}

async function readSeenIds(source: DeviceActivitySource): Promise<SeenIds | null> {
  try {
    const raw = await AsyncStorage.getItem(seenIdsKey(source));
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      !Array.isArray((parsed as SeenIds).ids)
    ) {
      return null;
    }
    return parsed as SeenIds;
  } catch {
    // A missing or corrupt set only costs the stability check, which is a
    // diagnostic. Never let it break a sync.
    return null;
  }
}

async function writeSeenIds(
  source: DeviceActivitySource,
  ids: string[]
): Promise<void> {
  const payload: SeenIds = {
    ids: ids.slice(0, SEEN_IDS_CAP),
    truncated: ids.length > SEEN_IDS_CAP,
  };
  await AsyncStorage.setItem(seenIdsKey(source), JSON.stringify(payload));
}

export const healthSync = {
  /** When this source last synced completely, or null if it never has. */
  async lastSyncedAt(source: DeviceActivitySource): Promise<Date | null> {
    try {
      const raw = await AsyncStorage.getItem(watermarkKey(source));
      if (!raw) return null;
      const parsed = new Date(raw);
      return Number.isNaN(parsed.getTime()) ? null : parsed;
    } catch {
      // A missing watermark only costs a wider re-read, which is idempotent.
      return null;
    }
  },

  async forget(source: DeviceActivitySource): Promise<void> {
    try {
      await AsyncStorage.removeItem(watermarkKey(source));
      await AsyncStorage.removeItem(seenIdsKey(source));
    } catch {
      // Nothing useful to do; the next sync simply re-reads more than it needs.
    }
  },

  /**
   * Read a window of device activity and hand it to the server (§15).
   *
   * Order matters: the app-level consent is checked *before* the OS
   * permission dialog. Being dropped into a system prompt before anyone has
   * explained why is the pattern §30 calls deceptive, and it also puts the
   * user's answer on record with the OS before Fitora has the right to store
   * anything they'd say yes to.
   *
   * On failure the watermark is left where it was, so the next attempt
   * re-reads the same window. That is the retry mechanism — deliberately not
   * the outbox. Queued writes exist for data that lives only in a tap; health
   * records are still on the device tomorrow, so re-reading them costs
   * nothing and storing hundreds of copies of them would add a second dedup
   * mechanism next to the `external_id` one the server already has.
   */
  async run(options: {
    provider: HealthProvider;
    hasWearableConsent: boolean;
    now?: Date;
  }): Promise<HealthSyncOutcome> {
    const { provider, hasWearableConsent } = options;
    const now = options.now ?? new Date();

    if (!hasWearableConsent) {
      return { kind: "consent_required" };
    }

    const granted = (await provider.hasPermissions()) || (await provider.requestPermissions());
    if (!granted) {
      return { kind: "permission_denied" };
    }

    const watermark = await healthSync.lastSyncedAt(provider.source);
    const previouslySent = await readSeenIds(provider.source);
    const since =
      watermark === null
        ? daysBefore(now, INITIAL_HISTORY_DAYS)
        : daysBefore(watermark, OVERLAP_DAYS);

    let read: DeviceActivityEntry[];
    try {
      read = await provider.readActivity(since, now);
    } catch (error) {
      return {
        kind: "failed",
        message: error instanceof Error ? error.message : "Could not read from your health app.",
        partial: false,
      };
    }

    const withinBounds = read.filter(isSyncableEntry);
    const dropped = read.length - withinBounds.length;
    const { unique: sendable, duplicates: duplicateIds } = dedupeById(withinBounds);
    const unstableIds = idsLookUnstable(sendable, watermark, previouslySent);

    if (sendable.length === 0) {
      // Nothing to send is still a successful sync of this window: the
      // watermark moves so the next run doesn't re-read it forever.
      await AsyncStorage.setItem(watermarkKey(provider.source), now.toISOString());
      return {
        kind: "synced",
        read: read.length,
        dropped,
        duplicateIds,
        created: 0,
        updated: 0,
        unstableIds,
      };
    }

    let created = 0;
    let updated = 0;
    let landed = 0;

    for (const page of chunk(sendable, MAX_ENTRIES_PER_SYNC)) {
      try {
        const result = await activityApi.sync(provider.source, page);
        created += result.created;
        updated += result.updated;
        landed += 1;
      } catch (error) {
        const message =
          error instanceof ApiError
            ? error.message
            : "Couldn't reach Fitora. Your activity is still on your device — this will retry.";
        return { kind: "failed", message, partial: landed > 0 };
      }
    }

    try {
      await AsyncStorage.setItem(watermarkKey(provider.source), now.toISOString());
      await writeSeenIds(provider.source, sendable.map((entry) => entry.external_id));
    } catch {
      // The data landed; only the bookmark didn't. The next sync re-reads a
      // wider window and the server dedups it.
    }

    return {
      kind: "synced",
      read: read.length,
      dropped,
      duplicateIds,
      created,
      updated,
      unstableIds,
    };
  },
};
