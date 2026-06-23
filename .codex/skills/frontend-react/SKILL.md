---
name: frontend-react
description: Use when modifying React components, hooks, context, state management, routing, forms, API calls, accessibility, or React performance.
---


# React Best Practices

## Component Design

- Prefer function components.
- Keep components focused: rendering, local interaction, or composition.
- Move business logic into hooks, services, or state machines where appropriate.
- Keep server state separate from local UI state.
- Prefer composition over deeply configurable mega-components.

## Hooks

- Follow the Rules of Hooks.
- Do not use effects for pure derived state; compute during render or memoize only when needed.
- Use `useMemo` and `useCallback` for measured or obvious referential-stability needs, not by default everywhere.
- Clean up subscriptions, timers, observers, and async effects.
- Avoid stale closures by managing dependency arrays correctly.

## State

- Use local state for local UI.
- Use context for low-frequency global concerns such as theme/auth metadata.
- Use Redux Toolkit, Zustand, or TanStack Query only if the repo already uses them or the complexity justifies it.
- Keep Redux slices small and normalized.
- Keep async API logic in thunks/services/query layer, not inside random components.

## Forms

- Validate at the client for UX and at the server for correctness.
- Keep form errors structured and field-specific.
- Avoid uncontrolled/controlled mismatches.

## Accessibility

- Use semantic HTML first.
- Ensure keyboard navigation works.
- Associate labels with inputs.
- Manage focus for dialogs, drawers, menus, and route transitions.
- Do not rely only on color to communicate state.

## Performance

- Avoid unnecessary global state updates.
- Virtualize large lists.
- Split large routes/components when it improves load time.
- Avoid heavy calculations during render.
- Use React DevTools/profiler for actual bottlenecks.

## Verification

```bash
npm run typecheck
npm run lint
npm run test
npm run build
```

## Anti-Patterns

- Fetching data in many nested components without caching/coordination.
- Effects that write derived state from props.
- Mutating state directly.
- Huge component files with API, validation, rendering, and business rules mixed together.
