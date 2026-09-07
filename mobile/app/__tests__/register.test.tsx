import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { ApiError } from "../../src/api/client";
import RegisterScreen from "../(auth)/register";

const mockRegister = jest.fn();
const mockReplace = jest.fn();

jest.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ register: mockRegister }),
}));

jest.mock("expo-router", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { Text } = require("react-native");
  return {
    router: { replace: (...a: unknown[]) => mockReplace(...a) },
    Link: ({ children }: { children: React.ReactNode }) => <Text>{children}</Text>,
  };
});

const VALID_EMAIL = "New.User@Example.com ";
const VALID_PASSWORD = "correct-horse-battery";

describe("RegisterScreen form validation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRegister.mockResolvedValue(undefined);
  });

  it("keeps submit disabled until both fields are valid", async () => {
    const view = await render(<RegisterScreen />);
    const button = view.getByText("Create account");

    await fireEvent.press(button);
    expect(mockRegister).not.toHaveBeenCalled();

    await fireEvent.changeText(view.getByPlaceholderText("Email"), "a@example.com");
    await fireEvent.press(button);
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("warns while the password is too short, and stops warning once it is long enough", async () => {
    const view = await render(<RegisterScreen />);
    const password = view.getByPlaceholderText("Password (min 8 characters)");

    await fireEvent.changeText(password, "short");
    expect(view.getByText(/at least 8 characters/i)).toBeTruthy();

    await fireEvent.changeText(password, VALID_PASSWORD);
    expect(view.queryByText(/at least 8 characters/i)).toBeNull();
  });

  it("does not warn about length before anything is typed", async () => {
    // An empty form should not greet the user with an error.
    const view = await render(<RegisterScreen />);

    expect(view.queryByText(/at least 8 characters/i)).toBeNull();
  });

  it("normalises the email before submitting", async () => {
    const view = await render(<RegisterScreen />);

    await fireEvent.changeText(view.getByPlaceholderText("Email"), VALID_EMAIL);
    await fireEvent.changeText(
      view.getByPlaceholderText("Password (min 8 characters)"),
      VALID_PASSWORD
    );
    await fireEvent.press(view.getByText("Create account"));

    await waitFor(() =>
      expect(mockRegister).toHaveBeenCalledWith("new.user@example.com", VALID_PASSWORD)
    );
  });

  it("navigates into the app on success", async () => {
    const view = await render(<RegisterScreen />);

    await fireEvent.changeText(view.getByPlaceholderText("Email"), "a@example.com");
    await fireEvent.changeText(
      view.getByPlaceholderText("Password (min 8 characters)"),
      VALID_PASSWORD
    );
    await fireEvent.press(view.getByText("Create account"));

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/(tabs)"));
  });

  it("shows the server's message and stays put when registration is refused", async () => {
    mockRegister.mockRejectedValue(new ApiError(409, "That email is already registered."));
    const view = await render(<RegisterScreen />);

    await fireEvent.changeText(view.getByPlaceholderText("Email"), "taken@example.com");
    await fireEvent.changeText(
      view.getByPlaceholderText("Password (min 8 characters)"),
      VALID_PASSWORD
    );
    await fireEvent.press(view.getByText("Create account"));

    await waitFor(() =>
      expect(view.getByText("That email is already registered.")).toBeTruthy()
    );
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("does not leak an unexpected error's internals to the user", async () => {
    mockRegister.mockRejectedValue(new Error("ECONNREFUSED 10.0.0.5:5432"));
    const view = await render(<RegisterScreen />);

    await fireEvent.changeText(view.getByPlaceholderText("Email"), "a@example.com");
    await fireEvent.changeText(
      view.getByPlaceholderText("Password (min 8 characters)"),
      VALID_PASSWORD
    );
    await fireEvent.press(view.getByText("Create account"));

    await waitFor(() => expect(view.getByText(/Unable to create your account/)).toBeTruthy());
    expect(view.queryByText(/ECONNREFUSED/)).toBeNull();
  });

  it("shows the health disclaimer up front", async () => {
    const view = await render(<RegisterScreen />);

    expect(view.getByText(/not medical advice/i)).toBeTruthy();
  });
});
