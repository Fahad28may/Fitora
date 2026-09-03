import { tokenStorage } from "../auth/tokenStorage";
import { API_BASE_URL } from "./config";
import type { TokenResponse } from "./types";

export class ApiError extends Error {
  status: number;
  // Raw `detail` field from the backend's error body — usually a string,
  // but some endpoints (e.g. unsafe goal targets) return a structured object.
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function rawRequest(
  path: string,
  options: RequestInit,
  accessToken?: string | null
): Promise<Response> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  return fetch(`${API_BASE_URL}${path}`, { ...options, headers });
}

// Coalesce concurrent 401s into a single refresh call instead of racing
// multiple refresh-token rotations against each other.
let refreshPromise: Promise<TokenResponse | null> | null = null;

async function refreshTokens(): Promise<TokenResponse | null> {
  const refreshToken = await tokenStorage.getRefreshToken();
  if (!refreshToken) return null;

  const response = await rawRequest("/api/v1/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    await tokenStorage.clear();
    return null;
  }
  const tokens = (await response.json()) as TokenResponse;
  await tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const accessToken = await tokenStorage.getAccessToken();
  let response = await rawRequest(path, options, accessToken);

  if (response.status === 401 && accessToken) {
    refreshPromise ??= refreshTokens().finally(() => {
      refreshPromise = null;
    });
    const refreshed = await refreshPromise;
    if (refreshed) {
      response = await rawRequest(path, options, refreshed.access_token);
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : undefined;
    const message =
      typeof detail === "string" ? detail : "Something went wrong. Please try again.";
    throw new ApiError(response.status, message, detail);
  }

  return body as T;
}
