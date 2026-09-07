import AsyncStorage from "@react-native-async-storage/async-storage";

import { ApiError, apiRequest } from "./client";

const STORAGE_KEY = "fitora.outbox.v1";

/**
 * A write that couldn't reach the server yet (§46).
 *
 * `idempotencyKey` is generated once, when the write is first attempted, and
 * reused on every retry. That is what makes flushing safe: a request that
 * actually succeeded but whose response was lost — the usual failure on a
 * flaky connection — replays into the same server-side entry instead of
 * logging the meal twice.
 */
export interface OutboxEntry {
  id: string;
  path: string;
  method: "POST";
  body: unknown;
  idempotencyKey: string;
  /** Shown to the user, e.g. "250 ml of water". */
  description: string;
  queuedAt: string;
  attempts: number;
}

function newId(): string {
  // Good enough for a local queue id: it only has to be unique within one
  // device's outbox, and it doubles as the idempotency key.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

async function readAll(): Promise<OutboxEntry[]> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as OutboxEntry[]) : [];
  } catch {
    // A corrupt queue must not brick the app. Losing unsent writes is bad;
    // refusing to start is worse.
    return [];
  }
}

async function writeAll(entries: OutboxEntry[]): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Storage full or unavailable — nothing useful to do here, and throwing
    // would turn a queued write into a crash.
  }
}

/**
 * A failure that means "the server said no", as opposed to "the network is
 * down". A rejected write must leave the queue: retrying a 422 forever would
 * block everything behind it.
 */
function isPermanentFailure(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  if (error.status === 401) return false; // token refresh may fix it
  if (error.status === 409) return true; // key already used — already landed
  return error.status >= 400 && error.status < 500;
}

export const outbox = {
  list: readAll,

  async count(): Promise<number> {
    return (await readAll()).length;
  },

  async clear(): Promise<void> {
    await AsyncStorage.removeItem(STORAGE_KEY);
  },

  /**
   * Send a write, queueing it if the network is unavailable.
   *
   * Returns the server's response when it goes through immediately, or null
   * when it was queued. The caller decides what to show — the entry is
   * pending, not lost.
   */
  async send<T>(
    path: string,
    body: unknown,
    description: string,
  ): Promise<T | null> {
    const idempotencyKey = newId();
    try {
      return await apiRequest<T>(path, {
        method: "POST",
        body: JSON.stringify(body),
        headers: { "Idempotency-Key": idempotencyKey },
      });
    } catch (error) {
      if (isPermanentFailure(error)) throw error;
      const entries = await readAll();
      entries.push({
        id: idempotencyKey,
        path,
        method: "POST",
        body,
        idempotencyKey,
        description,
        queuedAt: new Date().toISOString(),
        attempts: 1,
      });
      await writeAll(entries);
      return null;
    }
  },

  /**
   * Try to send everything queued, oldest first.
   *
   * Stops at the first network failure rather than hammering every entry
   * against a connection that is still down, and preserves order so a
   * dependent write never lands before the one it follows.
   */
  async flush(): Promise<{ sent: number; failed: number; remaining: number }> {
    const entries = await readAll();
    if (entries.length === 0) return { sent: 0, failed: 0, remaining: 0 };

    let sent = 0;
    let failed = 0;
    const remaining: OutboxEntry[] = [];

    for (const [index, entry] of entries.entries()) {
      try {
        await apiRequest(entry.path, {
          method: entry.method,
          body: JSON.stringify(entry.body),
          headers: { "Idempotency-Key": entry.idempotencyKey },
        });
        sent += 1;
      } catch (error) {
        if (isPermanentFailure(error)) {
          // The server rejected it for good. Drop it rather than retrying
          // forever and blocking everything behind it.
          failed += 1;
          continue;
        }
        // Still offline — keep this and everything after it, in order.
        remaining.push(...entries.slice(index));
        break;
      }
    }

    await writeAll(remaining);
    return { sent, failed, remaining: remaining.length };
  },
};
