import eslint from "@eslint/js";
import tseslint from "typescript-eslint";
import importPlugin from "eslint-plugin-import-x";
import googleConfig from "eslint-config-google";

const cleanGoogleRules = {...googleConfig.rules};
delete cleanGoogleRules["valid-jsdoc"];
delete cleanGoogleRules["require-jsdoc"];

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    plugins: {
      import: importPlugin,
    },
    languageOptions: {
      parserOptions: {
        project: ["tsconfig.json", "tsconfig.dev.json"],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      ...cleanGoogleRules,
      "quotes": ["error", "double"],
      "import/no-unresolved": 0,
      "indent": ["error", 2],
    },
  },
  {
    ignores: ["lib/**/*", "generated/**/*"],
  },
);
