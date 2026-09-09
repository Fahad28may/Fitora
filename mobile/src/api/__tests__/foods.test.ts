import { foodsApi } from "../foods";

const mockApiRequest = jest.fn();
jest.mock("../client", () => {
  const actual = jest.requireActual("../client");
  return { ...actual, apiRequest: (...args: unknown[]) => mockApiRequest(...args) };
});

beforeEach(() => {
  mockApiRequest.mockReset();
  mockApiRequest.mockResolvedValue({});
});

describe("foodsApi.search", () => {
  it("keeps the search term on the server by default", async () => {
    await foodsApi.search("chocolate spread");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "/api/v1/foods/search?q=chocolate%20spread",
    );
  });

  it("only reaches the external provider when explicitly asked", async () => {
    await foodsApi.search("chocolate spread", { includeExternal: true });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "/api/v1/foods/search?q=chocolate%20spread&include_external=true",
    );
  });

  it("does not opt in when the flag is explicitly false", async () => {
    await foodsApi.search("oats", { includeExternal: false });
    expect(mockApiRequest).toHaveBeenCalledWith("/api/v1/foods/search?q=oats");
  });

  it("encodes a term that would otherwise change the query string", async () => {
    await foodsApi.search("salt & pepper");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "/api/v1/foods/search?q=salt%20%26%20pepper",
    );
  });
});
