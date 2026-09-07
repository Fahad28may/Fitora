import { fireEvent, render } from "@testing-library/react-native";
import { Platform } from "react-native";

import { BarcodeScanner } from "../BarcodeScanner";

const mockUseCameraPermissions = jest.fn();
const mockOnBarcodeScanned = jest.fn();

jest.mock("expo-camera", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { View } = require("react-native");
  return {
    useCameraPermissions: () => mockUseCameraPermissions(),
    CameraView: (props: { onBarcodeScanned?: (e: { data: string }) => void }) => {
      mockOnBarcodeScanned.mockImplementation((data: string) =>
        props.onBarcodeScanned?.({ data })
      );
      return <View testID="camera-view" />;
    },
  };
});

const granted = { granted: true, canAskAgain: true };
const denied = { granted: false, canAskAgain: true };
const permanentlyDenied = { granted: false, canAskAgain: false };

describe("BarcodeScanner", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Platform.OS = "ios";
  });

  it("fires onScanned exactly once even though the camera reports continuously", async () => {
    // The camera calls onBarcodeScanned on every frame a code is visible, so
    // without the latch one scan would trigger dozens of network lookups.
    mockUseCameraPermissions.mockReturnValue([granted, jest.fn()]);
    const onScanned = jest.fn();
    await render(<BarcodeScanner onScanned={onScanned} onCancel={jest.fn()} />);

    mockOnBarcodeScanned("5000112637922");
    mockOnBarcodeScanned("5000112637922");
    mockOnBarcodeScanned("5000112637922");

    expect(onScanned).toHaveBeenCalledTimes(1);
    expect(onScanned).toHaveBeenCalledWith("5000112637922");
  });

  it("allows another scan after the user taps Scan again", async () => {
    mockUseCameraPermissions.mockReturnValue([granted, jest.fn()]);
    const onScanned = jest.fn();
    const view = await render(<BarcodeScanner onScanned={onScanned} onCancel={jest.fn()} />);

    mockOnBarcodeScanned("111111111");
    await fireEvent.press(view.getByText("Scan again"));
    mockOnBarcodeScanned("222222222");

    expect(onScanned).toHaveBeenCalledTimes(2);
    expect(onScanned).toHaveBeenLastCalledWith("222222222");
  });

  it("ignores scans while a lookup is already in flight", async () => {
    mockUseCameraPermissions.mockReturnValue([granted, jest.fn()]);
    const onScanned = jest.fn();
    await render(<BarcodeScanner onScanned={onScanned} onCancel={jest.fn()} isBusy />);

    mockOnBarcodeScanned("5000112637922");

    expect(onScanned).not.toHaveBeenCalled();
  });

  it("explains why the camera is needed before asking for permission", async () => {
    mockUseCameraPermissions.mockReturnValue([denied, jest.fn()]);
    const view = await render(<BarcodeScanner onScanned={jest.fn()} onCancel={jest.fn()} />);

    expect(view.getByText(/no image leaves your phone/i)).toBeTruthy();
    expect(view.getByText("Allow camera")).toBeTruthy();
  });

  it("requests permission when the user allows it", async () => {
    const request = jest.fn().mockResolvedValue({ granted: true });
    mockUseCameraPermissions.mockReturnValue([denied, request]);
    const view = await render(<BarcodeScanner onScanned={jest.fn()} onCancel={jest.fn()} />);

    await fireEvent.press(view.getByText("Allow camera"));

    expect(request).toHaveBeenCalled();
  });

  it("offers a way forward instead of a dead button when permission is permanently denied", async () => {
    mockUseCameraPermissions.mockReturnValue([permanentlyDenied, jest.fn()]);
    const view = await render(<BarcodeScanner onScanned={jest.fn()} onCancel={jest.fn()} />);

    expect(view.queryByText("Allow camera")).toBeNull();
    expect(view.getByText(/search for the food by name instead/i)).toBeTruthy();
  });

  it("falls back to a clear message on web rather than a broken camera view", async () => {
    Platform.OS = "web";
    mockUseCameraPermissions.mockReturnValue([granted, jest.fn()]);
    const view = await render(<BarcodeScanner onScanned={jest.fn()} onCancel={jest.fn()} />);

    expect(view.getByText(/needs a real camera/i)).toBeTruthy();
    expect(view.queryByTestId("camera-view")).toBeNull();
  });

  it("calls onCancel from the cancel control", async () => {
    mockUseCameraPermissions.mockReturnValue([granted, jest.fn()]);
    const onCancel = jest.fn();
    const view = await render(<BarcodeScanner onScanned={jest.fn()} onCancel={onCancel} />);

    await fireEvent.press(view.getByText("Cancel"));

    expect(onCancel).toHaveBeenCalled();
  });
});
