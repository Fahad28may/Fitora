import { apiRequest } from "./client";

export type ActivityType =
  | "walking"
  | "running"
  | "cycling"
  | "swimming"
  | "strength"
  | "sport"
  | "other";

export type ActivitySource = "manual" | "apple_health" | "health_connect" | "wearable";

/** Everything a device sync may claim as its origin. A sync cannot write `manual`. */
export type DeviceActivitySource = Exclude<ActivitySource, "manual">;

/**
 * Bounds mirrored from `backend/app/schemas/activity.py`.
 *
 * Duplicated deliberately rather than fetched: the server is still the
 * authority and rejects anything outside these, but a device feed that sends
 * one impossible record would otherwise fail a whole 500-entry batch with a
 * 422. Knowing the limits here lets the sync drop the bad record and deliver
 * the rest.
 */
export const ACTIVITY_LIMITS = {
  maxDurationMin: 1440,
  maxDistanceKm: 1000,
  maxSteps: 200_000,
  maxCaloriesBurned: 20_000,
  maxNotesLen: 500,
} as const;

/** Matches the server's `MAX_ENTRIES_PER_SYNC`; a longer feed pages through. */
export const MAX_ENTRIES_PER_SYNC = 500;

export interface ActivityEntryCreateRequest {
  logged_at: string;
  activity_type: ActivityType;
  duration_min: number;
  distance_km?: number | null;
  steps?: number | null;
  calories_burned?: number | null;
  notes?: string | null;
}

export interface ActivityEntryOut {
  id: string;
  logged_at: string;
  activity_type: ActivityType;
  duration_min: number;
  distance_km: number | null;
  steps: number | null;
  calories_burned: number | null;
  source: ActivitySource;
  notes: string | null;
  created_at: string;
}

/** One record as a health app reported it, keyed by the device's own id. */
export interface DeviceActivityEntry {
  external_id: string;
  logged_at: string;
  activity_type: ActivityType;
  duration_min: number;
  distance_km?: number | null;
  steps?: number | null;
  calories_burned?: number | null;
  notes?: string | null;
}

export interface ActivitySyncResult {
  source: ActivitySource;
  received: number;
  created: number;
  updated: number;
}

function withinBounds(value: number | null | undefined, max: number): boolean {
  if (value === null || value === undefined) return true;
  return Number.isFinite(value) && value >= 0 && value <= max;
}

/**
 * Whether the server will accept this record, checked against the same bounds
 * it enforces.
 *
 * Used to filter a device feed before sending. A health app reporting a
 * 40-hour run is a bug somewhere on the device; dropping that one record is
 * better than losing the whole batch it arrived in.
 */
export function isSyncableEntry(entry: DeviceActivityEntry): boolean {
  if (!entry.external_id || entry.external_id.length > 128) return false;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(entry.logged_at)) return false;
  if (!Number.isInteger(entry.duration_min)) return false;
  if (entry.duration_min <= 0 || entry.duration_min > ACTIVITY_LIMITS.maxDurationMin) {
    return false;
  }
  if (!withinBounds(entry.distance_km, ACTIVITY_LIMITS.maxDistanceKm)) return false;
  if (!withinBounds(entry.steps, ACTIVITY_LIMITS.maxSteps)) return false;
  if (!withinBounds(entry.calories_burned, ACTIVITY_LIMITS.maxCaloriesBurned)) return false;
  if ((entry.notes?.length ?? 0) > ACTIVITY_LIMITS.maxNotesLen) return false;
  return true;
}

export const activityApi = {
  listForDate: (isoDate: string): Promise<ActivityEntryOut[]> =>
    apiRequest<ActivityEntryOut[]>(`/api/v1/activity-entries?date=${isoDate}`),

  create: (payload: ActivityEntryCreateRequest): Promise<ActivityEntryOut> =>
    apiRequest<ActivityEntryOut>("/api/v1/activity-entries", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  remove: (id: string): Promise<void> =>
    apiRequest<void>(`/api/v1/activity-entries/${id}`, { method: "DELETE" }),

  /**
   * Hand one page of device-reported activity to the server (§15).
   *
   * Idempotent by `external_id`, so re-sending a window that was already
   * delivered updates those rows rather than duplicating them. Callers should
   * page at `MAX_ENTRIES_PER_SYNC`.
   */
  sync: (
    source: DeviceActivitySource,
    entries: DeviceActivityEntry[]
  ): Promise<ActivitySyncResult> =>
    apiRequest<ActivitySyncResult>("/api/v1/activity-entries/sync", {
      method: "POST",
      body: JSON.stringify({ source, entries }),
    }),
};
