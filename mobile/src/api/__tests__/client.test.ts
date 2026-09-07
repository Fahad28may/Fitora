import { ApiError, apiRequest } from "../client";

jest.mock("../../auth/tokenStorage", () => ({
  tokenStorage: {
    getAccessToken: jest.fn(),
    getRefreshToken: jest.fn(),
    setTokens: jest.fn(),
    clear: jest.fn(),
  },
}));

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { tokenStorage } = require("../../auth/tokenStorage") as {
  tokenStorage: {
    getAccessToken: jest.Mock;
    getRefreshToken: jest.Mock;
    setTokens: jest.Mock;
    clear: jest.Mock;
  };
};

function jsonResponse(status: number, body: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as unknown as Response;
}

function emptyResponse(status: number): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: new Headers(),
    json: async () => null,
  } as unknown as Response;
}

describe("apiRequest", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    tokenStorage.getAccessToken.mockResolvedValue("access-token");
    tokenStorage.getRefreshToken.mockResolvedValue("refresh-token");
  });

  it("returns the parsed body on success", async () => {
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(200, { id: "abc" }));

    await expect(apiRequest<{ id: string }>("/thing")).resolves.toEqual({ id: "abc" });
  });

  it("attaches the bearer token", async () => {
    const fetchMock = jest.fn().mockResolvedValue(jsonResponse(200, {}));
    global.fetch = fetchMock;

    await apiRequest("/thing");

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer access-token");
  });

  it("returns undefined for a 204 rather than trying to parse a body", async () => {
    global.fetch = jest.fn().mockResolvedValue(emptyResponse(204));

    await expect(apiRequest("/thing", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("throws ApiError carrying the status and the backend's detail", async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValue(jsonResponse(422, { detail: "Quantity must be positive." }));

    await expect(apiRequest("/thing")).rejects.toMatchObject({
      status: 422,
      message: "Quantity must be positive.",
    });
    await expect(apiRequest("/thing")).rejects.toBeInstanceOf(ApiError);
  });

  it("falls back to a generic message when detail is not a string", async () => {
    // Some endpoints (unsafe goal targets) return a structured detail object;
    // the raw object must not be rendered at the user as a message.
    global.fetch = jest
      .fn()
      .mockResolvedValue(jsonResponse(422, { detail: { reason: "too_aggressive" } }));

    await expect(apiRequest("/thing")).rejects.toMatchObject({
      status: 422,
      message: "Something went wrong. Please try again.",
      detail: { reason: "too_aggressive" },
    });
  });

  it("refreshes once on a 401 and retries the original request", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(
        jsonResponse(200, {
          access_token: "new-access",
          refresh_token: "new-refresh",
          expires_in: 900,
        })
      )
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    global.fetch = fetchMock;

    await expect(apiRequest("/thing")).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toContain("/api/v1/auth/refresh");
    const retryHeaders = fetchMock.mock.calls[2][1].headers as Headers;
    expect(retryHeaders.get("Authorization")).toBe("Bearer new-access");
    expect(tokenStorage.setTokens).toHaveBeenCalledWith("new-access", "new-refresh");
  });

  it("coalesces concurrent 401s into a single refresh", async () => {
    // Racing refresh-token rotations against each other would revoke the
    // token the other request is about to use.
    let refreshCalls = 0;
    global.fetch = jest.fn().mockImplementation(async (url: string) => {
      if (typeof url === "string" && url.includes("/auth/refresh")) {
        refreshCalls += 1;
        return jsonResponse(200, {
          access_token: "new-access",
          refresh_token: "new-refresh",
          expires_in: 900,
        });
      }
      const headers = new Headers();
      return refreshCalls === 0 ? jsonResponse(401, { detail: "expired" }) : jsonResponse(200, { ok: true, headers });
    });

    await Promise.all([apiRequest("/a"), apiRequest("/b"), apiRequest("/c")]);

    expect(refreshCalls).toBe(1);
  });

  it("clears stored tokens when the refresh itself fails", async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "refresh rejected" }));

    await expect(apiRequest("/thing")).rejects.toBeInstanceOf(ApiError);
    expect(tokenStorage.clear).toHaveBeenCalled();
  });

  it("does not attempt a refresh when there was no token to begin with", async () => {
    tokenStorage.getAccessToken.mockResolvedValue(null);
    const fetchMock = jest.fn().mockResolvedValue(jsonResponse(401, { detail: "nope" }));
    global.fetch = fetchMock;

    await expect(apiRequest("/thing")).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
