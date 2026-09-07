import { ApiError } from "../client";
import { outbox } from "../outbox";

const mockApiRequest = jest.fn();
jest.mock("../client", () => {
  const actual = jest.requireActual("../client");
  return {
    ...actual,
    apiRequest: (...args: unknown[]) => mockApiRequest(...args),
  };
});

// Prefixed with `mock` so jest's module factory is allowed to reference it.
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

const OFFLINE = new TypeError("Network request failed");

describe("outbox", () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    mockStore.clear();
  });

  it("sends straight through when the network is up", async () => {
    mockApiRequest.mockResolvedValue({ id: "abc" });

    const result = await outbox.send("/api/v1/water-entries", { amount_ml: 250 }, "250 ml");

    expect(result).toEqual({ id: "abc" });
    expect(await outbox.count()).toBe(0);
  });

  it("attaches an idempotency key to every write", async () => {
    mockApiRequest.mockResolvedValue({});

    await outbox.send("/api/v1/water-entries", {}, "water");

    const headers = mockApiRequest.mock.calls[0][1].headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeTruthy();
  });

  it("queues the write instead of losing it when the network is down", async () => {
    mockApiRequest.mockRejectedValue(OFFLINE);

    const result = await outbox.send("/api/v1/water-entries", { amount_ml: 250 }, "250 ml");

    expect(result).toBeNull();
    expect(await outbox.count()).toBe(1);
    expect((await outbox.list())[0].description).toBe("250 ml");
  });

  it("replays a queued write with the SAME key it was queued with", async () => {
    // This is what makes flushing safe: a request that actually succeeded but
    // whose response was lost replays into the same server-side entry.
    mockApiRequest.mockRejectedValueOnce(OFFLINE);
    await outbox.send("/api/v1/water-entries", { amount_ml: 250 }, "250 ml");
    const queuedKey = (await outbox.list())[0].idempotencyKey;

    mockApiRequest.mockResolvedValue({});
    await outbox.flush();

    const flushHeaders = mockApiRequest.mock.calls[1][1].headers as Record<string, string>;
    expect(flushHeaders["Idempotency-Key"]).toBe(queuedKey);
  });

  it("empties the queue once everything is sent", async () => {
    mockApiRequest.mockRejectedValue(OFFLINE);
    await outbox.send("/a", {}, "one");
    await outbox.send("/b", {}, "two");
    expect(await outbox.count()).toBe(2);

    mockApiRequest.mockReset();
    mockApiRequest.mockResolvedValue({});
    const result = await outbox.flush();

    expect(result).toEqual({ sent: 2, failed: 0, remaining: 0 });
    expect(await outbox.count()).toBe(0);
  });

  it("keeps the queue when the connection is still down", async () => {
    mockApiRequest.mockRejectedValue(OFFLINE);
    await outbox.send("/a", {}, "one");

    const result = await outbox.flush();

    expect(result.sent).toBe(0);
    expect(result.remaining).toBe(1);
    expect(await outbox.count()).toBe(1);
  });

  it("stops at the first network failure and preserves order", async () => {
    mockApiRequest.mockRejectedValue(OFFLINE);
    await outbox.send("/a", {}, "one");
    await outbox.send("/b", {}, "two");
    await outbox.send("/c", {}, "three");

    mockApiRequest.mockReset();
    mockApiRequest.mockResolvedValueOnce({}).mockRejectedValue(OFFLINE);
    await outbox.flush();

    const remaining = await outbox.list();
    expect(remaining.map((e) => e.description)).toEqual(["two", "three"]);
  });

  it("drops a write the server permanently rejects rather than blocking the queue", async () => {
    // Retrying a 422 forever would stall everything queued behind it.
    mockApiRequest.mockRejectedValue(OFFLINE);
    await outbox.send("/bad", {}, "invalid");
    await outbox.send("/good", {}, "fine");

    mockApiRequest.mockReset();
    mockApiRequest
      .mockRejectedValueOnce(new ApiError(422, "Invalid request"))
      .mockResolvedValue({});
    const result = await outbox.flush();

    expect(result).toEqual({ sent: 1, failed: 1, remaining: 0 });
    expect(await outbox.count()).toBe(0);
  });

  it("treats a 409 as already landed and drops it", async () => {
    mockApiRequest.mockRejectedValue(OFFLINE);
    await outbox.send("/a", {}, "one");

    mockApiRequest.mockReset();
    mockApiRequest.mockRejectedValue(new ApiError(409, "key already used"));
    const result = await outbox.flush();

    expect(result.failed).toBe(1);
    expect(await outbox.count()).toBe(0);
  });

  it("keeps a 401 queued, since a token refresh may fix it", async () => {
    mockApiRequest.mockRejectedValue(OFFLINE);
    await outbox.send("/a", {}, "one");

    mockApiRequest.mockReset();
    mockApiRequest.mockRejectedValue(new ApiError(401, "expired"));
    await outbox.flush();

    expect(await outbox.count()).toBe(1);
  });

  it("does not queue a write the server rejected outright", async () => {
    // A 422 on the first attempt is the server saying no, not the network
    // failing — the user needs to see the error, not a silent queue entry.
    mockApiRequest.mockRejectedValue(new ApiError(422, "Quantity must be positive."));

    await expect(outbox.send("/a", {}, "one")).rejects.toBeInstanceOf(ApiError);
    expect(await outbox.count()).toBe(0);
  });

  it("survives a corrupt queue rather than bricking the app", async () => {
    mockStore.set("fitora.outbox.v1", "{not json");

    expect(await outbox.count()).toBe(0);
    expect(await outbox.list()).toEqual([]);
  });

  it("flushing an empty queue does nothing", async () => {
    const result = await outbox.flush();

    expect(result).toEqual({ sent: 0, failed: 0, remaining: 0 });
    expect(mockApiRequest).not.toHaveBeenCalled();
  });
});
