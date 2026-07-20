const browserGlobals = {
  AbortController: "readonly",
  CSS: "readonly",
  Element: "readonly",
  HTMLInputElement: "readonly",
  HTMLSelectElement: "readonly",
  HTMLTextAreaElement: "readonly",
  Node: "readonly",
  Set: "readonly",
  URL: "readonly",
  WeakMap: "readonly",
  chrome: "readonly",
  clearTimeout: "readonly",
  crypto: "readonly",
  document: "readonly",
  fetch: "readonly",
  globalThis: "readonly",
  location: "readonly",
  setTimeout: "readonly",
};

export default [
  {
    files: ["*.js"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "script",
      globals: browserGlobals,
    },
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
    rules: {
      curly: "error",
      eqeqeq: "error",
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-undef": "error",
      "no-unused-vars": ["error", { "argsIgnorePattern": "^_" }],
      "no-var": "error",
      "prefer-const": "error",
    },
  },
  {
    files: ["tests/*.mjs"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: {
        Buffer: "readonly",
        URL: "readonly",
        console: "readonly",
        process: "readonly",
      },
    },
    rules: {
      curly: "error",
      eqeqeq: "error",
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-undef": "error",
      "no-unused-vars": "error",
      "no-var": "error",
      "prefer-const": "error",
    },
  },
];
