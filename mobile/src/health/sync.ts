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

const WATERMARK_KEY_PREFIX = "fitora.health.lastSync.v1";

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
      created: number;
      updated: number;
    }
  | { kind: "failed"; message: string; /** Pages that did land before the failure. */ partial: boolean };

function watermarkKey(source: DeviceActivitySource): string {
  return `${WATERMARK_KEY_PREFIX}.${source}`;
}

function daysBefore(date: Date, days: number): Date {
  return new Date(date.getTime() - days * 24 * 60 * 60 * 1000);
}

function chunk<T>(items: T[], size: number): T[][] {
  const pages: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    pages.push(items.slice(i, i + size));
  }
  return pages;
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

    const sendable = read.filter(isSyncableEntry);
    const dropped = read.length - sendable.length;

    if (sendable.length === 0) {
      // Nothing to send is still a successful sync of this window: the
      // watermark moves so the next run doesn't re-read it forever.
      await AsyncStorage.setItem(watermarkKey(provider.source), now.toISOString());
      return { kind: "synced", read: read.length, dropped, created: 0, updated: 0 };
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
    } catch {
      // The data landed; only the bookmark didn't. The next sync re-reads a
      // wider window and the server dedups it.
    }

    return { kind: "synced", read: read.length, dropped, created, updated };
  },
};
