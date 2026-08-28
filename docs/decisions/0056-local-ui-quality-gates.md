# 56. Run UI quality gates locally

Date: 2026-08-28

## Status

Accepted

## Context

Tessera's cockpit is the product, but its component states were only exercised through full pages. The repository had no automated WCAG scan, no isolated component catalogue, and almost no screenshot regression coverage. The project is intentionally local-first and cannot depend on a hosted review service.

## Decision

Use Storybook with the official Next.js Vite adapter as a local component workshop, including the official accessibility addon. Use `@axe-core/playwright` in the existing Playwright suite for automated WCAG checks on representative cockpit routes. Keep deterministic Playwright screenshots in the repository for desktop and 390 px mobile viewports.

These tools are development dependencies only. Storybook runs on localhost, visual baselines are generated locally, and no cloud account, telemetry service, or hosted publishing step is required by the workflow.

## Consequences

Critical visual states can be reviewed without manufacturing backend conditions, accessibility violations fail a named test, and responsive regressions become reviewable diffs. The trade-off is a larger frontend development dependency graph and a small maintenance cost when shared providers or design tokens change.
