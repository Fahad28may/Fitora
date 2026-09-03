import { apiRequest } from "./client";
import type { AuthResponse, UserOut } from "./types";

export const authApi = {
  register: (email: string, password: string): Promise<AuthResponse> =>
    apiRequest<AuthResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string): Promise<AuthResponse> =>
    apiRequest<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: (): Promise<UserOut> => apiRequest<UserOut>("/api/v1/auth/me"),

  logout: (refreshToken: string): Promise<void> =>
    apiRequest<void>("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
};
