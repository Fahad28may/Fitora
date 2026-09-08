import type { DeviceActivityEntry, DeviceActivitySource } from "../api/activity";

/**
 * A source of device-recorded activity — Apple Health, Health Connect, or a
 * wearable's own SDK.
 *
 * Reading any of them needs native code, which Expo Go cannot load. This
 * interface is the seam: everything above it (consent ordering, sync windows,
 * paging, dedup, error handling) is ordinary TypeScript and is tested against
 * a fake. A build that ships the native modules registers a real
 * implementation and changes nothing else.
 *
 * Read-only by construction: there is no write method, because Fitora reads
 * activity from the device and never writes back (§15).
 */
export interface HealthProvider {
  /** What the server should record as the origin of these records. */
  readonly source: DeviceActivitySource;
  /** User-facing name, e.g. "Apple Health". Shown before any permission ask. */
  readonly name: string;

  /**
   * Whether this device can supply data at all — the OS supports it, and on
   * Android, whether the Health Connect app is actually installed.
   */
  isAvailable(): Promise<boolean>;

  /** Whether the OS has already granted the read scopes Fitora needs. */
  hasPermissions(): Promise<boolean>;

  /**
   * Ask the OS for read access to steps, distance, workouts and active
   * energy — and nothing else (§15: minimum scopes).
   *
   * Must only be called after the user has agreed in-app, never as the first
   * thing they see.
   */
  requestPermissions(): Promise<boolean>;

  /**
   * Records overlapping `[since, until]`, one per device record.
   *
   * `external_id` must be the device's own identifier for the record —
   * HealthKit's UUID, Health Connect's record id — never one synthesised from
   * a timestamp, which would change when the device revises a record and turn
   * the server's dedup into duplicates.
   */
  readActivity(since: Date, until: Date): Promise<DeviceActivityEntry[]>;
}

/**
 * Why no provider is usable, when none is.
 *
 * `no_native_module` is the state this build is actually in, and the UI says
 * so plainly rather than showing a Connect button that cannot work.
 */
export type HealthUnavailableReason =
  | "unsupported_platform"
  | "no_native_module"
  | "not_installed";

export type HealthProviderStatus =
  | { kind: "available"; provider: HealthProvider }
  | { kind: "unavailable"; reason: HealthUnavailableReason };

let registered: HealthProvider | null = null;

/**
 * Install the platform's provider. Called once at startup by a build that
 * includes the native modules; never called in Expo Go.
 */
export function registerHealthProvider(provider: HealthProvider | null): void {
  registered = provider;
}

/** Test seam and startup reset — forgets any registered provider. */
export function clearHealthProvider(): void {
  registered = null;
}

export async function getHealthProviderStatus(
  platformOs: string
): Promise<HealthProviderStatus> {
  if (platformOs !== "ios" && platformOs !== "android") {
    return { kind: "unavailable", reason: "unsupported_platform" };
  }
  if (registered === null) {
    return { kind: "unavailable", reason: "no_native_module" };
  }
  if (!(await registered.isAvailable())) {
    // The module is present but the platform can't serve it — on Android the
    // usual cause is that the Health Connect app itself isn't installed.
    return { kind: "unavailable", reason: "not_installed" };
  }
  return { kind: "available", provider: registered };
}
