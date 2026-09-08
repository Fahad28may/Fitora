import { fireEvent, render, waitFor } from "@testing-library/react-native";

import {
  clearHealthProvider,
  registerHealthProvider,
  type HealthProvider,
} from "../../health/provider";
import { HealthSyncCard } from "../HealthSyncCard";

const mockRun = jest.fn();
const mockLastSyncedAt = jest.fn();
jest.mock("../../health/sync", () => ({
  healthSync: {
    run: (...a: unknown[]) => mockRun(...a),
    lastSyncedAt: (...a: unknown[]) => mockLastSyncedAt(...a),
  },
}));

function fakeProvider(): HealthProvider {
  return {
    source: "health_connect",
    name: "Health Connect",
    isAvailable: jest.fn(async () => true),
    hasPermissions: jest.fn(async () => true),
    requestPermissions: jest.fn(async () => true),
    readActivity: jest.fn(async () => []),
  };
}

describe("HealthSyncCard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clearHealthProvider();
    mockLastSyncedAt.mockResolvedValue(null);
  });

  afterEach(() => clearHealthProvider());

  it("says plainly that this build can't read a health app, with no dead Connect button", async () => {
    const view = await render(<HealthSyncCard hasWearableConsent />);

    await waitFor(() =>
      expect(view.getByText(/can't read Apple Health or Health Connect/i)).toBeTruthy()
    );
    expect(view.queryByText("Sync now")).toBeNull();
  });

  it("offers a sync once a provider is registered", async () => {
    registerHealthProvider(fakeProvider());

    const view = await render(<HealthSyncCard hasWearableConsent />);

    await waitFor(() => expect(view.getByText("Sync now")).toBeTruthy());
    expect(view.getByText(/only reads/i)).toBeTruthy();
  });

  it("points at the consent switch when consent is missing", async () => {
    registerHealthProvider(fakeProvider());
    mockRun.mockResolvedValue({ kind: "consent_required" });

    const view = await render(<HealthSyncCard hasWearableConsent={false} />);
    await waitFor(() => expect(view.getByText("Sync now")).toBeTruthy());
    await fireEvent.press(view.getByText("Sync now"));

    await waitFor(() =>
      expect(view.getByText(/Read data from wearables.*above first/s)).toBeTruthy()
    );
  });

  it("reports records the device got wrong instead of hiding them", async () => {
    registerHealthProvider(fakeProvider());
    mockRun.mockResolvedValue({ kind: "synced", read: 5, dropped: 2, created: 3, updated: 0 });

    const view = await render(<HealthSyncCard hasWearableConsent />);
    await waitFor(() => expect(view.getByText("Sync now")).toBeTruthy());
    await fireEvent.press(view.getByText("Sync now"));

    await waitFor(() =>
      expect(view.getByText(/2 skipped as out of range/)).toBeTruthy()
    );
  });

  it("says a failed sync will retry rather than implying data was lost", async () => {
    registerHealthProvider(fakeProvider());
    mockRun.mockResolvedValue({
      kind: "failed",
      message: "Couldn't reach Fitora.",
      partial: false,
    });

    const view = await render(<HealthSyncCard hasWearableConsent />);
    await waitFor(() => expect(view.getByText("Sync now")).toBeTruthy());
    await fireEvent.press(view.getByText("Sync now"));

    await waitFor(() => expect(view.getByText(/Couldn't reach Fitora/)).toBeTruthy());
  });
});
