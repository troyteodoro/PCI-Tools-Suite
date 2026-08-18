// ESLint 9 flat config.
//
// Ordering is load-bearing: typescript-eslint's `eslint-recommended` overrides ship
// inside `configs.recommended` and must follow `js.configs.recommended` so they can
// switch off the base rules TypeScript already enforces. Chief among them is `no-undef`,
// which is why this file needs no browser/node globals list and no `globals` package.

import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**'] },

  js.configs.recommended,
  ...tseslint.configs.recommended,

  {
    files: ['**/*.{ts,tsx}'],
    plugins: { 'react-hooks': reactHooks },
    rules: {
      // react-hooks 5.1 has no flat preset; spread the legacy recommended set.
      ...reactHooks.configs.recommended.rules,

      // recommended ships this as a warning, and `--max-warnings 0` fails on warnings
      // anyway, so the honest severity is error.
      'react-hooks/exhaustive-deps': 'error',

      // tsconfig sets verbatimModuleSyntax: a type imported as a value survives into the
      // emitted module and can fail at runtime. This rule is not stylistic here.
      '@typescript-eslint/consistent-type-imports': ['error', { fixStyle: 'inline-type-imports' }],

      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],

      // Structured logs are a backend concern; a console call in the UI is debris.
      'no-console': ['error', { allow: ['warn', 'error'] }],
    },
  },

  // Config files run in Node and are outside the app's module graph.
  {
    files: ['*.config.{js,ts}', 'vite.config.ts'],
    rules: { 'no-console': 'off' },
  },
);
