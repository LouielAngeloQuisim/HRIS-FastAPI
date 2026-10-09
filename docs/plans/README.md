# Plans and implementation evidence

A plan names the objective, touched files, business/security constraints, regression tests, verification commands and rollout risks. Keep unrelated implementation concerns in separate PRs.

- [Runtime migration evidence](runtime-upgrades-2026-10-02.md): individually reviewed replacements delivered through PR #68.
- [Attendance-driven payroll implementation](attendance-driven-payroll-implementation.md) and its [calculation comparison worksheet](payroll-calculator-comparison.md): payroll scope, current gaps, and the human acceptance comparison.
- New module plans follow the [module guide](../modules/README.md) and [feature workflow](../feature-development-workflow.md).
- [ROADMAP](../ROADMAP.md) is the numbered cleanup authority. Phase JSON files describe feature planning and may lag source code.

Update plans with observed results. Do not label a task complete while CI, deployment verification or required user decisions remain outstanding. Preserve completed plans for provenance and index them in [archive](../archive/README.md).
