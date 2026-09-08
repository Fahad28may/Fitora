import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { Alert } from "react-native";

import { ApiError } from "../../src/api/client";
import SettingsScreen from "../settings";

const mockAccountApi = {
  getConsents: jest.fn(),
  setConsent: jest.fn(),
  export: jest.fn(),
  deleteAccount: jest.fn(),
};

jest.mock("../../src/api/account", () => ({
  accountApi: {
    getConsents: (...a: unknown[]) => mockAccountApi.getConsents(...a),
    setConsent: (...a: unknown[]) => mockAccountApi.setConsent(...a),
    export: (...a: unknown[]) => mockAccountApi.export(...a),
    deleteAccount: (...a: unknown[]) => mockAccountApi.deleteAccount(...a),
  },
  DELETE_CONFIRMATION_PHRASE: "DELETE MY ACCOUNT",
}));

const mockLogout = jest.fn();
jest.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: { email: "a@example.com" }, logout: mockLogout }),
}));

jest.mock("expo-router", () => ({
  router: { replace: jest.fn(), back: jest.fn(), push: jest.fn() },
}));

jest.mock("expo-sharing", () => ({ isAvailableAsync: jest.fn().mockResolvedValue(false) }));
jest.mock("expo-file-system", () => ({
  Paths: { cache: "/cache" },
  File: class {
    uri = "/cache/fitora-export.json";
    exists = false;
    create() {}
    write() {}
    delete() {}
  },
}));

const CONSENT_STATE = {
  policy_version: "2026-09-07-draft",
  consents: {
    health_data: false,
    ai_processing: false,
    wearable_access: false,
    analytics: false,
  },
};

describe("Settings → Privacy", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAccountApi.getConsents.mockResolvedValue(CONSENT_STATE);
    mockAccountApi.setConsent.mockResolvedValue(undefined);
    mockAccountApi.export.mockResolvedValue({ account: {} });
  });

  it("shows every consent as off by default — nothing is pre-selected", async () => {
    const view = await render(<SettingsScreen />);

    await waitFor(() => expect(view.getByText("Store my health data")).toBeTruthy());
    for (const label of [
      "Store my health data",
      "Use AI features",
      "Read data from wearables",
      "Optional product analytics",
    ]) {
      expect(view.getByLabelText(label).props.value).toBe(false);
    }
  });

  it("records a consent decision when a switch is turned on", async () => {
    const view = await render(<SettingsScreen />);
    await waitFor(() => expect(view.getByText("Use AI features")).toBeTruthy());

    await fireEvent(view.getByLabelText("Use AI features"), "valueChange", true);

    await waitFor(() =>
      expect(mockAccountApi.setConsent).toHaveBeenCalledWith("ai_processing", true)
    );
  });

  it("reverts the switch when the write fails, rather than lying about it", async () => {
    mockAccountApi.setConsent.mockRejectedValue(new ApiError(503, "server down"));
    const view = await render(<SettingsScreen />);
    await waitFor(() => expect(view.getByText("Use AI features")).toBeTruthy());

    await fireEvent(view.getByLabelText("Use AI features"), "valueChange", true);

    await waitFor(() => expect(view.getByText("server down")).toBeTruthy());
    expect(view.getByLabelText("Use AI features").props.value).toBe(false);
  });

  it("says plainly that unbuilt features collect nothing", async () => {
    const view = await render(<SettingsScreen />);

    await waitFor(() => expect(view.getByText(/Fitora collects no analytics today/)).toBeTruthy());
  });

  it("does not offer a device sync this build cannot perform", async () => {
    // The wearable consent switch is real and the server accepts device
    // activity, but no build shipped so far can read a health app. Saying so
    // beats a Connect button that quietly does nothing.
    const view = await render(<SettingsScreen />);

    await waitFor(() =>
      expect(view.getByText(/can't read Apple Health or Health Connect/i)).toBeTruthy()
    );
    expect(view.queryByText("Sync now")).toBeNull();
  });

  it("exports data when asked", async () => {
    const view = await render(<SettingsScreen />);

    await fireEvent.press(view.getByLabelText("Export my data"));

    await waitFor(() => expect(mockAccountApi.export).toHaveBeenCalled());
  });

  it("surfaces an export failure instead of silently doing nothing", async () => {
    mockAccountApi.export.mockRejectedValue(new ApiError(500, "export blew up"));
    const view = await render(<SettingsScreen />);

    await fireEvent.press(view.getByLabelText("Export my data"));

    await waitFor(() => expect(view.getByText("export blew up")).toBeTruthy());
  });
});

describe("Settings → delete account form validation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAccountApi.getConsents.mockResolvedValue(CONSENT_STATE);
    mockAccountApi.deleteAccount.mockResolvedValue(undefined);
    jest.spyOn(Alert, "alert").mockImplementation(((
      _t: string,
      _m: string,
      buttons: { text: string; onPress?: () => void }[]
    ) => {
      buttons.find((b) => b.text === "Delete forever")?.onPress?.();
    }) as unknown as typeof Alert.alert);
  });

  async function openDeleteForm() {
    const view = await render(<SettingsScreen />);
    await fireEvent.press(view.getByLabelText("Start deleting my account"));
    return view;
  }

  it("keeps deletion disabled until both password and exact phrase are given", async () => {
    const view = await openDeleteForm();
    const button = view.getByLabelText("Delete my account permanently");

    expect(button.props.accessibilityState?.disabled).toBe(true);

    await fireEvent.changeText(view.getByLabelText("Your password"), "hunter2");
    expect(button.props.accessibilityState?.disabled).toBe(true);
  });

  it("rejects a near-miss confirmation phrase", async () => {
    const view = await openDeleteForm();

    await fireEvent.changeText(view.getByLabelText("Your password"), "hunter2");
    await fireEvent.changeText(
      view.getByLabelText("Type DELETE MY ACCOUNT to confirm"),
      "delete my account"
    );

    await fireEvent.press(view.getByLabelText("Delete my account permanently"));
    expect(mockAccountApi.deleteAccount).not.toHaveBeenCalled();
  });

  it("deletes only after password, exact phrase, and the confirm dialog", async () => {
    const view = await openDeleteForm();

    await fireEvent.changeText(view.getByLabelText("Your password"), "hunter2");
    await fireEvent.changeText(
      view.getByLabelText("Type DELETE MY ACCOUNT to confirm"),
      "DELETE MY ACCOUNT"
    );
    await fireEvent.press(view.getByLabelText("Delete my account permanently"));

    await waitFor(() =>
      expect(mockAccountApi.deleteAccount).toHaveBeenCalledWith("hunter2", "DELETE MY ACCOUNT")
    );
    expect(Alert.alert).toHaveBeenCalled();
  });

  it("shows the server's reason when deletion is refused", async () => {
    mockAccountApi.deleteAccount.mockRejectedValue(
      new ApiError(401, "Password is incorrect.")
    );
    const view = await openDeleteForm();

    await fireEvent.changeText(view.getByLabelText("Your password"), "wrong");
    await fireEvent.changeText(
      view.getByLabelText("Type DELETE MY ACCOUNT to confirm"),
      "DELETE MY ACCOUNT"
    );
    await fireEvent.press(view.getByLabelText("Delete my account permanently"));

    await waitFor(() => expect(view.getByText("Password is incorrect.")).toBeTruthy());
    expect(mockLogout).not.toHaveBeenCalled();
  });
});
