---
name: frontend-vue-vite
description: Use when modifying Vue 3, Composition API, Pinia, Vue Router, Single File Components, Vite config, frontend env variables, or Vue TypeScript checks.
---


# Vue 3 / Vite Best Practices

## Vue Component Design

- Prefer Composition API for new Vue 3 code unless the repo standard is Options API.
- Use `<script setup lang="ts">` for concise typed components when supported.
- Keep templates declarative and simple.
- Move reusable logic into composables.
- Move app-wide state to Pinia or the existing store pattern.
- Keep server state and UI state distinct.

## Props and Emits

- Type props and emits explicitly.
- Do not mutate props directly.
- Use `computed` for derived values.
- Use watchers only for side effects, not simple derivation.
- Keep two-way binding explicit with `v-model` conventions.

## Routing

- Use route-level code splitting where appropriate.
- Keep auth guards server-backed; UI guards improve UX but are not security.
- Validate route params before using them in API calls.

## Vite

- Vite transpiles TypeScript but does not replace a full typecheck. Always run `vue-tsc`/`tsc` via project scripts.
- Only variables prefixed for client exposure should be used in browser code, for example `VITE_`.
- Never put server secrets into client env variables.
- Keep build aliases consistent with `tsconfig` paths.
- Use `import.meta.env` intentionally and type env variables when practical.

## Styling

- Prefer component-scoped styles or the repository’s design system.
- Avoid deep selectors unless needed for third-party components.
- Keep responsive behavior explicit.

## Verification

```bash
npm run typecheck
npm run lint
npm run test
npm run build
```

Common equivalents:

```bash
npx vue-tsc --noEmit
npx vite build
```

## Anti-Patterns

- Large smart components that own API, validation, business rules, and rendering.
- Overusing watchers.
- Mutating reactive objects from unrelated modules.
- Assuming `vite build` alone catches type errors.
