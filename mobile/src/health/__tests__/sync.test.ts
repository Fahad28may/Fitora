import type { DeviceActivityEntry } from "../../api/activity";
import { ApiError } from "../../api/client";
import type { HealthProvider } from "../provider";
import { INITIAL_HISTORY_DAYS, OVERLAP_DAYS, healthSync } from "../sync";

const mockSync = jest.fn();
jest.mock("../../api/activity", () => {
  const actual = jest.requireActual("../../api/activity");
  return {
    ...actual,
    activityApi: { ...actual.activityApi, sync: (...args: unknown[]) => mockSync(...args) },
  };
});

const mockStore = new Map<string, string>();
jest.mock("@react-native-async-storage/async-storage", () => ({
  getItem: jest.fn(async (k: string) => mockStore.get(k) ?? null),
  setItem: jest.fn(async (k: string, v: string) => {
    mockStore.set(k, v);
  }),
  removeItem: jest.fn(async (k: string) => {
    mockStore.delete(k);
  }),
}));

const NOW = new Date("2026-09-08T12:00:00.000Z");

function entry(overrides: Partial<DeviceActivityEntry> = {}): DeviceActivityEntry {
  return {
    external_id: "HKWorkout-1",
    logged_at: "2026-09-07",
    activity_type: "running",
    duration_min: 32,
    distance_km: 5.4,
    steps: 6100,
    calories_burned: 340,
    ...overrides,
  };
}

/** A stand-in for HealthKit / Health Connect that records how it was called. */
function fakeProvider(overrides: Partial<HealthProvider> = {}): HealthProvider {
  return {
    source: "apple_health",
    name: "Apple Health",
    isAvailable: jest.fn(async () => true),
    hasPermissions: jest.fn(async () => true),
    requestPermissions: jest.fn(async () => true),
    readActivity: jest.fn(async () => [entry()]),
    ...overrides,
  };
}

describe("healthSync.run", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore.clear();
    mockSync.mockResolvedValue({
      source: "apple_health",
      received: 1,
      created: 1,
      updated: 0,
    });
  });

  it("refuses to read anything without the app-level consent", async () => {
    const provider = fakeProvider();

    const outcome = await healthSync.run({
      provider,
      hasWearableConsent: false,
      now: NOW,
    });

    expect(outcome).toEqual({ kind: "consent_required" });
    // The point of the ordering: the OS is never asked, so the user isn't
    // dropped into a system dialog before anyone explained why (§30).
    expect(provider.requestPermissions).not.toHaveBeenCalled();
    expect(provider.readActivity).not.toHaveBeenCalled();
    expect(mockSync).not.toHaveBeenCalled();
  });

  it("stops when the device refuses permission", async () => {
    const provider = fakeProvider({
      hasPermissions: jest.fn(async () => false),
      requestPermissions: jest.fn(async () => false),
    });

    const outcome = await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    expect(outcome).toEqual({ kind: "permission_denied" });
    expect(provider.readActivity).not.toHaveBeenCalled();
  });

  it("only prompts when permission isn't already granted", async () => {
    const provider = fakeProvider();

    await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    expect(provider.requestPermissions).not.toHaveBeenCalled();
  });

  it("reads a bounded window on the first sync, not all of history", async () => {
    const provider = fakeProvider();

    await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    const [since, until] = (provider.readActivity as jest.Mock).mock.calls[0];
    const days = (NOW.getTime() - (since as Date).getTime()) / 86_400_000;
    expect(days).toBeCloseTo(INITIAL_HISTORY_DAYS);
    expect(until).toEqual(NOW);
  });

  it("re-reads an overlap after the first sync, because devices revise records", async () => {
    const provider = fakeProvider();
    await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    const later = new Date(NOW.getTime() + 3 * 86_400_000);
    await healthSync.run({ provider, hasWearableConsent: true, now: later });

    const [since] = (provider.readActivity as jest.Mock).mock.calls[1];
    const overlapDays = (NOW.getTime() - (since as Date).getTime()) / 86_400_000;
    expect(overlapDays).toBeCloseTo(OVERLAP_DAYS);
  });

  it("sends the device's own id so a re-sync updates instead of duplicating", async () => {
    const provider = fakeProvider();

    await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    const [source, entries] = mockSync.mock.calls[0];
    expect(source).toBe("apple_health");
    expect(entries[0].external_id).toBe("HKWorkout-1");
  });

  it("drops an impossible record rather than losing the batch it arrived in", async () => {
    const provider = fakeProvider({
      readActivity: jest.fn(async () => [
        entry({ external_id: "good" }),
        // A 40-hour run: a bug on the device. Sending it would 422 the whole
        // request and lose the good record with it.
        entry({ external_id: "bad", duration_min: 2400 }),
      ]),
    });
    mockSync.mockResolvedValue({ source: "apple_health", received: 1, created: 1, updated: 0 });

    const outcome = await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    expect(outcome).toMatchObject({ kind: "synced", read: 2, dropped: 1 });
    const [, entries] = mockSync.mock.calls[0];
    expect(entries).toHaveLength(1);
    expect(entries[0].external_id).toBe("good");
  });

  it("pages a long feed at the server's batch limit", async () => {
    const many = Array.from({ length: 1200 }, (_, i) =>
      entry({ external_id: `HKWorkout-${i}` })
    );
    const provider = fakeProvider({ readActivity: jest.fn(async () => many) });
    mockSync.mockResolvedValue({ source: "apple_health", received: 500, created: 500, updated: 0 });

    await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    expect(mockSync).toHaveBeenCalledTimes(3);
    expect(mockSync.mock.calls[0][1]).toHaveLength(500);
    expect(mockSync.mock.calls[2][1]).toHaveLength(200);
  });

  it("leaves the watermark alone when a page fails, so the window is retried", async () => {
    const provider = fakeProvider();
    mockSync.mockRejectedValue(new TypeError("Network request failed"));

    const outcome = await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    expect(outcome).toMatchObject({ kind: "failed", partial: false });
    expect(await healthSync.lastSyncedAt("apple_health")).toBeNull();
  });

  it("reports a partial failure when some pages landed", async () => {
    const many = Array.from({ length: 600 }, (_, i) => entry({ external_id: `w-${i}` }));
    const provider = fakeProvider({ readActivity: jest.fn(async () => many) });
    mockSync
      .mockResolvedValueOnce({ source: "apple_health", received: 500, created: 500, updated: 0 })
      .mockRejectedValueOnce(new TypeError("Network request failed"));

    const outcome = await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    expect(outcome).toMatchObject({ kind: "failed", partial: true });
    expect(await healthSync.lastSyncedAt("apple_health")).toBeNull();
  });

  it("surfaces the server's own message when it rejects the sync", async () => {
    const provider = fakeProvider();
    mockSync.mockRejectedValue(
      new ApiError(403, 'Turn on "Read data from wearables" in Settings → Privacy before syncing device activity.')
    );

    const outcome = await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    expect(outcome).toMatchObject({ kind: "failed" });
    expect((outcome as { message: string }).message).toContain("Read data from wearables");
  });

  it("advances the watermark on an empty window so it isn't re-read forever", async () => {
    const provider = fakeProvider({ readActivity: jest.fn(async () => []) });

    const outcome = await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    expect(outcome).toEqual({ kind: "synced", read: 0, dropped: 0, created: 0, updated: 0 });
    expect(mockSync).not.toHaveBeenCalled();
    expect(await healthSync.lastSyncedAt("apple_health")).toEqual(NOW);
  });

  it("survives the device throwing while reading", async () => {
    const provider = fakeProvider({
      readActivity: jest.fn(async () => {
        throw new Error("Health Connect unavailable");
      }),
    });

    const outcome = await healthSync.run({ provider, hasWearableConsent: true, now: NOW });

    expect(outcome).toMatchObject({ kind: "failed", partial: false });
    expect(await healthSync.lastSyncedAt("apple_health")).toBeNull();
  });

  it("keeps a separate watermark per source", async () => {
    await healthSync.run({ provider: fakeProvider(), hasWearableConsent: true, now: NOW });

    expect(await healthSync.lastSyncedAt("apple_health")).toEqual(NOW);
    expect(await healthSync.lastSyncedAt("health_connect")).toBeNull();
  });

  it("forgets a watermark on request, so the next sync re-reads from scratch", async () => {
    await healthSync.run({ provider: fakeProvider(), hasWearableConsent: true, now: NOW });
    await healthSync.forget("apple_health");

    expect(await healthSync.lastSyncedAt("apple_health")).toBeNull();
  });
});
