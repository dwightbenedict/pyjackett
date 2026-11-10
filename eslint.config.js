import js from "@eslint/js";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["src/pyjackett/web/static/js/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: globals.browser,
    },
    rules: {
      "max-len": ["error", { code: 79, ignoreUrls: true, ignoreStrings: true }],
      "max-lines-per-function": ["warn", { max: 50, skipComments: true }],
      complexity: ["warn", 10],
      eqeqeq: "error",
      "no-var": "error",
      "prefer-const": "error",
      curly: ["error", "multi-line"],
    },
  },
];
