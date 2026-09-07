import { apiRequest } from "./client";
import type { ConsentState, ConsentType, SecurityEvent } from "./types";

export const accountApi = {
  /** The full data export as a parsed object — the caller writes it to a file. */
  export: (): Promise<Record<string, unknown>> =>
    apiRequest<Record<string, unknown>>("/api/v1/account/export"),

  getConsents: (): Promise<ConsentState> =>
    apiRequest<ConsentState>("/api/v1/account/consents"),

  setConsent: (consentType: ConsentType, granted: boolean): Promise<unknown> =>
    apiRequest("/api/v1/account/consents", {
      method: "PUT",
      body: JSON.stringify({ consent_type: consentType, granted }),
    }),

  securityEvents: (): Promise<SecurityEvent[]> =>
    apiRequest<SecurityEvent[]>("/api/v1/account/security-events"),

  /**
   * Irreversible. The backend requires the exact phrase as well as the
   * password, so the confirmation is not something the UI can quietly supply
   * on the user's behalf — they have to type it.
   */
  deleteAccount: (password: string, confirmation: string): Promise<void> =>
    apiRequest<void>("/api/v1/account", {
      method: "DELETE",
      body: JSON.stringify({ password, confirmation }),
    }),
};

export const DELETE_CONFIRMATION_PHRASE = "DELETE MY ACCOUNT";
