// Reserved for global test setup. Intentionally minimal: jest-expo's preset
// already mocks the native modules this app touches.
//
// Note for anyone writing tests here: in @testing-library/react-native v14
// `render` and `fireEvent` are ASYNC. Forgetting to await render gives you a
// promise with no query methods and the confusing error
// "view.getByText is not a function".

// AsyncStorage is a native module, so any test that renders a screen reaching
// it (the outbox, the health-sync watermark) fails to even load without this.
// Registered globally rather than per-suite: a screen test shouldn't have to
// know which module three levels down happens to persist something. Suites
// that assert on stored values still install their own in-memory mock, which
// takes precedence.
jest.mock(
  "@react-native-async-storage/async-storage",
  () => require("@react-native-async-storage/async-storage/jest/async-storage-mock")
);
