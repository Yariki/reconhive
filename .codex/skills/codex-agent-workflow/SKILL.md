---
name: codex-agent-workflow
description: Use when setting up Codex instructions, AGENTS.md, reusable skills, plans, or agent review workflows.
---


# Codex Agent Workflow Skill

## When to Use

Use this skill when creating or editing `AGENTS.md`, `PLANS.md`, code-review instructions, or reusable Codex skills.

## Best Practices

- Keep `AGENTS.md` concise and operational.
- Put durable repository rules in `AGENTS.md`.
- Put long task procedures in focused skill files.
- Put one-off execution details in `PLANS.md`.
- Use nested `AGENTS.override.md` only when a subdirectory genuinely needs different rules.
- Encode verification commands and done criteria explicitly.
- Convert repeated mistakes into new rules.

## AGENTS.md Should Include

- Repository layout.
- Setup commands.
- Build/test/lint/typecheck commands.
- Architecture boundaries.
- Security constraints.
- Database migration rules.
- PR/review expectations.
- Definition of done.

## Skill Design Rules

- One skill equals one workflow.
- The `description` must include trigger words.
- Keep instructions executable and specific.
- Include commands, file paths, and anti-patterns.
- Avoid vague preferences such as “write clean code” unless converted into measurable checks.

## Review Before Finish

- Does the instruction help Codex decide what to do differently?
- Is it short enough to fit context budgets?
- Are commands realistic for this repo?
- Are dangerous operations guarded by approval language?
