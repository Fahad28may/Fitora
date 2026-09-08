import {
  ACTIVITY_LIMITS,
  activityApi,
  isSyncableEntry,
  type DeviceActivityEntry,
} from "../activity";

const mockApiRequest = jest.fn();
jest.mock("../client", () => {
  const actual = jest.requireActual("../client");
  return { ...actual, apiRequest: (...args: unknown[]) => mockApiRequest(...args) };
});

function entry(overrides: Partial<DeviceActivityEntry> = {}): DeviceActivityEntry {
  return {
    external_id: "HKWorkout-1",
    logged_at: "2026-09-07",
    activity_type: "running",
    duration_min: 32,
    ...overrides,
  };
}

describe("isSyncableEntry", () => {
  it("accepts an ordinary record", () => {
    expect(isSyncableEntry(entry())).toBe(true);
  });

  it("rejects a record with no device id, which would defeat dedup", () => {
    expect(isSyncableEntry(entry({ external_id: "" }))).toBe(false);
    expect(isSyncableEntry(entry({ external_id: "x".repeat(129) }))).toBe(false);
  });

  it.each([
    ["a zero-length activity", { duration_min: 0 }],
    ["a 40-hour run", { duration_min: ACTIVITY_LIMITS.maxDurationMin + 1 }],
    ["a fractional duration the server stores as an integer", { duration_min: 12.5 }],
    ["an impossible distance", { distance_km: ACTIVITY_LIMITS.maxDistanceKm + 1 }],
    ["an impossible step count", { steps: ACTIVITY_LIMITS.maxSteps + 1 }],
    ["an impossible calorie burn", { calories_burned: ACTIVITY_LIMITS.maxCaloriesBurned + 1 }],
    ["a negative distance", { distance_km: -1 }],
    ["a NaN the device produced", { distance_km: Number.NaN }],
    ["an over-long note", { notes: "x".repeat(ACTIVITY_LIMITS.maxNotesLen + 1) }],
    ["a timestamp where a date belongs", { logged_at: "2026-09-07T10:00:00Z" }],
  ])("rejects %s", (_label, overrides) => {
    expect(isSyncableEntry(entry(overrides as Partial<DeviceActivityEntry>))).toBe(false);
  });

  it("treats absent optional fields as fine", () => {
    expect(
      isSyncableEntry(entry({ distance_km: null, steps: undefined, calories_burned: null }))
    ).toBe(true);
  });
});

describe("activityApi", () => {
  beforeEach(() => jest.clearAllMocks());

  it("scopes the day list to a date", async () => {
    mockApiRequest.mockResolvedValue([]);
    await activityApi.listForDate("2026-09-08");
    expect(mockApiRequest).toHaveBeenCalledWith("/api/v1/activity-entries?date=2026-09-08");
  });

  it("posts a sync to the device endpoint, never the manual one", async () => {
    mockApiRequest.mockResolvedValue({ source: "apple_health", received: 1, created: 1, updated: 0 });

    await activityApi.sync("apple_health", [entry()]);

    const [path, options] = mockApiRequest.mock.calls[0];
    expect(path).toBe("/api/v1/activity-entries/sync");
    expect(JSON.parse(options.body as string)).toEqual({
      source: "apple_health",
      entries: [entry()],
    });
  });
});
