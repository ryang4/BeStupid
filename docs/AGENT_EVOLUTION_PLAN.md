# Agent Evolution Plan

This document tracks the implementation path for the assistant upgrades discussed on 2026-02-19.

## Objective

Build a personal, high-agency operator that:

- runs reliably while mobile
- self-updates behavior based on outcomes
- keeps private context private
- publishes public goal tracking to the Hugo site

## Phase 1 (Implemented in this PR)

### Personality onboarding

- add `/onboard` to configure per-chat assistant style
- persist profile in private storage (`HISTORY_DIR`)
- inject profile into system prompt every run

### Self-update policy loop

- add per-chat policy store (`agent_policies.json`)
- add `self_update_policy` tool so the model can update behavior rules/focus
- inject self-updated policy into the system prompt every run
- add `/policy` and `/resetpolicy` for transparency and control

## Phase 2 (Next)

### Always-on reliability

- move Telegram bot to webhook mode
- run on stable hosted runtime with health checks and restart policy
- add uptime + queue monitoring for missed mobile interactions

### Structured source of truth

- introduce canonical daily state in `data/` (JSON)
- render markdown logs from structured state
- stop parsing markdown as primary data transport

## Phase 3 (Next)

### Public/private projection layer

- explicit projection step:
  - private state -> redacted public summaries
  - private state -> private memory/operating context
- add validation to prevent private fields from entering `content/`

### Active intervention engine

- rules for automatic escalation (sleep debt, missed workouts, stalled priorities)
- adaptive task load + reminders based on compliance trends
- intervention logs for auditability

## Success Metrics

- >99% bot availability across mobile usage windows
- >90% days with complete structured check-ins
- measurable reduction in task rollover streaks
- zero private-data leaks into Hugo `content/`
