// Reserved for global test setup. Intentionally minimal: jest-expo's preset
// already mocks the native modules this app touches.
//
// Note for anyone writing tests here: in @testing-library/react-native v14
// `render` and `fireEvent` are ASYNC. Forgetting to await render gives you a
// promise with no query methods and the confusing error
// "view.getByText is not a function".
