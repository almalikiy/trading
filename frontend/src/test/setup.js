import "@testing-library/jest-dom";

if (!globalThis.localStorage || typeof globalThis.localStorage.clear !== "function") {
	const store = {};
	globalThis.localStorage = {
		getItem: (key) => (Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null),
		setItem: (key, value) => {
			store[key] = String(value);
		},
		removeItem: (key) => {
			delete store[key];
		},
		clear: () => {
			Object.keys(store).forEach((key) => delete store[key]);
		},
	};
}
