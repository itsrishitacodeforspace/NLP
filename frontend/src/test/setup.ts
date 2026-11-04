import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { afterEach } from 'vitest';

// The app uses react-query; its default 5000ms wait-for timeouts are too
// eager for jsdom + retry=1. 3000ms is generous for our (mostly mocked) tests.
configure({ asyncUtilTimeout: 3000 });

// Reset the DOM between tests so component renders never leak into each other.
afterEach(() => {
  cleanup();
});

// jsdom does not implement matchMedia (used by ThemeProvider).
if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

// This jsdom build does not expose window.localStorage (a real browser always
// does). AuthProvider/ThemeProvider read the auth token from it, so without a
// stand-in every storage-touching test throws. Provide an in-memory Storage —
// same rationale as the matchMedia polyfill above.
if (typeof window !== 'undefined' && !window.localStorage) {
  const store = new Map<string, string>();
  const storage: Storage = {
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size;
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(window, 'localStorage', {
    value: storage,
    writable: true,
    configurable: true,
  });
}
