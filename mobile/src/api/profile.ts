import { apiRequest } from "./client";
import type { ProfileOut, ProfileUpdateRequest } from "./types";

export const profileApi = {
  get: (): Promise<ProfileOut> => apiRequest<ProfileOut>("/api/v1/profile"),

  update: (payload: ProfileUpdateRequest): Promise<ProfileOut> =>
    apiRequest<ProfileOut>("/api/v1/profile", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};
