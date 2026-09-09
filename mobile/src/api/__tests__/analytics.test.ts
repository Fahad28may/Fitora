import { analyticsApi } from "../analytics";

const mockApiRequest = jest.fn();
jest.mock("../client", () => {
  const actual = jest.requireActual("../client");
  return { ...actual, apiRequest: (...args: unknown[]) => mockApiRequest(...args) };
});

beforeEach(() => {
  mockApiRequest.mockReset();
  mockApiRequest.mockResolvedValue({});
});

describe("analyticsApi", () => {
  it("requests the summary with the server's default window when none is given", async () => {
    await analyticsApi.summary();
    expect(mockApiRequest).toHaveBeenCalledWith("/api/v1/analytics/summary");
  });

  it("passes a requested window through", async () => {
    await analyticsApi.summary(90);
    expect(mockApiRequest).toHaveBeenCalledWith("/api/v1/analytics/summary?days=90");
  });

  it("reads adaptive targets from the advisory endpoint", async () => {
    await analyticsApi.adaptiveTargets();
    expect(mockApiRequest).toHaveBeenCalledWith("/api/v1/analytics/adaptive-targets");
  });

  it("never issues a write for adaptive targets", async () => {
    await analyticsApi.adaptiveTargets();
    // The suggestion is advisory on both sides: applying it means creating a
    // goal, which runs the server's safety check.
    expect(mockApiRequest).toHaveBeenCalledWith(expect.any(String));
    expect(mockApiRequest.mock.calls[0]).toHaveLength(1);
  });
});
