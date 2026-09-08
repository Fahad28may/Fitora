import {
  clearHealthProvider,
  getHealthProviderStatus,
  registerHealthProvider,
  type HealthProvider,
} from "../provider";

function fakeProvider(isAvailable: boolean): HealthProvider {
  return {
    source: "health_connect",
    name: "Health Connect",
    isAvailable: jest.fn(async () => isAvailable),
    hasPermissions: jest.fn(async () => true),
    requestPermissions: jest.fn(async () => true),
    readActivity: jest.fn(async () => []),
  };
}

describe("health provider resolution", () => {
  afterEach(() => clearHealthProvider());

  it("reports no native module when none is registered", async () => {
    // This is the state this build is actually in: the app runs in Expo Go,
    // which cannot load HealthKit or Health Connect.
    expect(await getHealthProviderStatus("ios")).toEqual({
      kind: "unavailable",
      reason: "no_native_module",
    });
  });

  it("reports an unsupported platform on web", async () => {
    registerHealthProvider(fakeProvider(true));

    expect(await getHealthProviderStatus("web")).toEqual({
      kind: "unavailable",
      reason: "unsupported_platform",
    });
  });

  it("distinguishes a missing companion app from a missing module", async () => {
    registerHealthProvider(fakeProvider(false));

    expect(await getHealthProviderStatus("android")).toEqual({
      kind: "unavailable",
      reason: "not_installed",
    });
  });

  it("hands back a registered, available provider", async () => {
    const provider = fakeProvider(true);
    registerHealthProvider(provider);

    expect(await getHealthProviderStatus("android")).toEqual({ kind: "available", provider });
  });
});
