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
