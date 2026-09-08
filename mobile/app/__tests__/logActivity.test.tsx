import { fireEvent, render, waitFor } from "@testing-library/react-native";

import LogActivityScreen from "../log-activity";

const mockActivityApi = {
  listForDate: jest.fn(),
  remove: jest.fn(),
};
jest.mock("../../src/api/activity", () => {
  const actual = jest.requireActual("../../src/api/activity");
  return {
    ...actual,
    activityApi: {
      listForDate: (...a: unknown[]) => mockActivityApi.listForDate(...a),
      remove: (...a: unknown[]) => mockActivityApi.remove(...a),
    },
  };
});

const mockSend = jest.fn();
jest.mock("../../src/api/outbox", () => ({
  outbox: { send: (...a: unknown[]) => mockSend(...a) },
}));

jest.mock("expo-router", () => ({ router: { back: jest.fn(), push: jest.fn() } }));

function anEntry(overrides: Record<string, unknown> = {}) {
  return {
    id: "e1",
    logged_at: "2026-09-08",
    activity_type: "running",
    duration_min: 32,
    distance_km: 5.4,
    steps: 6100,
    calories_burned: 340,
    source: "manual",
    notes: null,
    created_at: "2026-09-08T10:00:00Z",
    ...overrides,
  };
}

describe("Log activity", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockActivityApi.listForDate.mockResolvedValue([]);
    mockSend.mockResolvedValue(anEntry());
  });

  it("logs an activity through the outbox, so a flaky tap can't double-log", async () => {
    const view = await render(<LogActivityScreen />);

    await fireEvent.changeText(view.getByLabelText("Minutes"), "30");
    await fireEvent.press(view.getByLabelText("Log this activity"));

    await waitFor(() => expect(mockSend).toHaveBeenCalled());
    const [path, body] = mockSend.mock.calls[0];
    expect(path).toBe("/api/v1/activity-entries");
    expect(body).toMatchObject({ activity_type: "walking", duration_min: 30 });
  });

  it("sends the selected type", async () => {
    const view = await render(<LogActivityScreen />);

    await fireEvent.press(view.getByLabelText("Cycling"));
    await fireEvent.changeText(view.getByLabelText("Minutes"), "45");
    await fireEvent.press(view.getByLabelText("Log this activity"));

    await waitFor(() => expect(mockSend).toHaveBeenCalled());
    expect(mockSend.mock.calls[0][1]).toMatchObject({ activity_type: "cycling" });
  });

  it("refuses to log without a duration", async () => {
    const view = await render(<LogActivityScreen />);

    await fireEvent.press(view.getByLabelText("Log this activity"));

    await waitFor(() =>
      expect(view.getByText("Enter how many minutes it lasted.")).toBeTruthy()
    );
    expect(mockSend).not.toHaveBeenCalled();
  });

  it("rejects a duration longer than a day rather than letting the server 422", async () => {
    const view = await render(<LogActivityScreen />);

    await fireEvent.changeText(view.getByLabelText("Minutes"), "2400");
    await fireEvent.press(view.getByLabelText("Log this activity"));

    await waitFor(() =>
      expect(view.getByText("That's longer than a day — check the minutes.")).toBeTruthy()
    );
    expect(mockSend).not.toHaveBeenCalled();
  });

  it("reports a typo'd number instead of silently dropping the field", async () => {
    const view = await render(<LogActivityScreen />);

    await fireEvent.changeText(view.getByLabelText("Minutes"), "30");
    await fireEvent.changeText(view.getByLabelText("Distance in kilometres"), "5,4");
    await fireEvent.press(view.getByLabelText("Log this activity"));

    await waitFor(() =>
      expect(view.getByText("Distance, steps and calories need to be numbers.")).toBeTruthy()
    );
    expect(mockSend).not.toHaveBeenCalled();
  });

  it("omits optional fields that were left blank", async () => {
    const view = await render(<LogActivityScreen />);

    await fireEvent.changeText(view.getByLabelText("Minutes"), "30");
    await fireEvent.press(view.getByLabelText("Log this activity"));

    await waitFor(() => expect(mockSend).toHaveBeenCalled());
    expect(mockSend.mock.calls[0][1]).toMatchObject({
      distance_km: null,
      steps: null,
      calories_burned: null,
    });
  });

  it("says where each entry came from, so a watch's numbers aren't mistaken for typed ones", async () => {
    mockActivityApi.listForDate.mockResolvedValue([
      anEntry({ id: "a", source: "manual" }),
      anEntry({ id: "b", source: "apple_health" }),
    ]);

    const view = await render(<LogActivityScreen />);

    await waitFor(() => expect(view.getByText("Typed by you")).toBeTruthy());
    expect(view.getByText("From Apple Health")).toBeTruthy();
  });

  it("does not claim a calorie burn it didn't calculate", async () => {
    const view = await render(<LogActivityScreen />);

    await waitFor(() =>
      expect(
        view.getByText(/Fitora doesn't calculate calorie burn/i)
      ).toBeTruthy()
    );
  });

  it("deletes an entry", async () => {
    mockActivityApi.listForDate.mockResolvedValue([anEntry()]);
    mockActivityApi.remove.mockResolvedValue(undefined);

    const view = await render(<LogActivityScreen />);
    await waitFor(() => expect(view.getByLabelText("Delete running entry")).toBeTruthy());
    await fireEvent.press(view.getByLabelText("Delete running entry"));

    await waitFor(() => expect(mockActivityApi.remove).toHaveBeenCalledWith("e1"));
  });
});
