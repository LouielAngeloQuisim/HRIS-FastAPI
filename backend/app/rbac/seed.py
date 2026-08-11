"""Seed data for modules, submodules, and default roles.

**Modules and submodules** are recovered from the legacy source, not invented:

- The 5 main modules are the 5 array columns on `MainModules.php`:
  `project`, `humanres`, `administration`, `payroll`, `emp_leaves`.
- The 24 submodules are the 24 array columns on `SubModules.php`.
- The parent of each submodule is taken from the legacy sidebar tree
  (analysis/07 §2.6.1), because the legacy schema had no parent link at all -
  `MainModules` held a flat 1:1 to a single `SubModules` row. The sidebar
  groups all 24 under exactly these 5 headings.

**Roles** could not be recovered: the legacy repo has no fixtures or seed
migrations and the real list lived only in the production database
(analysis/05 §B.9). The codes below are a new default set, grounded in the
three codes that do appear in the legacy source/templates - `SADM` and `ADM`
(analysis/07 §2.6.1 "Roles and Access" guard) and `SUR` (hardcoded at
`ManpowerController.php:173,271` for every auto-provisioned employee).

Seeding is idempotent: it inserts what is missing and leaves existing rows
alone, so it is safe to run on every startup.
"""

from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.rbac.models import (
    ACTION_COLUMN,
    Module,
    PermissionAction,
    Role,
    RolePermission,
)

# --- Action shorthands ------------------------------------------------------
FULL: tuple[str, ...] = ("view", "add", "edit", "delete")
CONTRIBUTE: tuple[str, ...] = ("view", "add", "edit")
VIEW_ONLY: tuple[str, ...] = ("view",)
NONE: tuple[str, ...] = ()

SUPER_ADMIN_ROLE_CODE = "SADM"
# The legacy code auto-assigned to every rank-and-file employee account.
DEFAULT_EMPLOYEE_ROLE_CODE = "SUR"


# --- Legacy code collisions -------------------------------------------------
# `payroll` and `emp_leaves` each appear as BOTH a column on MainModules.php
# and a column on SubModules.php. In the legacy schema those lived in two
# separate tables so the clash was invisible; normalising them into one
# `module` table with globally unique codes surfaces it, and
# require_permission() takes a single string so the codes must disambiguate.
#
# Resolution: the MAIN module keeps the legacy code (the sidebar guards read
# `main_module_access.payroll` / `.emp_leaves`, so those are the structural
# names), and the two colliding SUBmodules are renamed after the routes they
# actually guard. Roadmap §4 sanctions clean names plus a documented mapping;
# this is that mapping, and Phase 6's ETL must apply it.
LEGACY_SUBMODULE_CODE_MAP: dict[str, str] = {
    # legacy SubModules column -> new module code
    "payroll": "employee_payroll",  # the "Payroll" page, /employee-payroll
    "emp_leaves": "employee_leaves",  # the "Employee Leaves" page, /employee-leaves/
}


# --- Modules ----------------------------------------------------------------
# (code, display name) in sidebar order.
MAIN_MODULES: list[tuple[str, str]] = [
    ("project", "Project Management"),
    ("humanres", "Human Resources"),
    ("administration", "Administration"),
    ("payroll", "Payroll Administration"),
    ("emp_leaves", "Leave Administration"),
]

# Parent code -> [(submodule code, display name)], in sidebar order.
SUBMODULES: dict[str, list[tuple[str, str]]] = {
    "project": [
        ("projects", "Projects"),
        ("emp_project", "Employee Projects"),
        ("category", "Categories"),
    ],
    "humanres": [
        ("daily_time_record", "Daily Time Records"),
        ("emp_list", "Employees"),
        ("emp_task", "Employee Tasks"),
    ],
    "administration": [
        ("division", "Division"),
        ("department", "Department"),
        ("subdivision", "Subdivisions"),
        ("phase", "Phase"),
        ("owner", "Owner"),
        ("models", "Models & Facilities"),
        ("model_types", "Model Types"),
        ("emp_settings", "Employee Settings"),
        ("shifts", "Shifts"),
        ("project_type", "Project Types"),
    ],
    "payroll": [
        ("sss_config", "SSS Configuration"),
        ("pagibig_config", "Pag-IBIG Configuration"),
        ("bir_config", "BIR Configuration"),
        ("philhealth_config", "PhilHealth Configuration"),
        ("employee_payroll", "Payroll"),
        ("payroll_reports", "Payroll Reports"),
    ],
    "emp_leaves": [
        ("leave_policy", "Leave Policy"),
        ("employee_leaves", "Employee Leaves"),
        ("holiday_config", "Holiday Configuration"),
        ("leave_request", "Leave Request"),
        ("leave_calendar", "Leave Calendar"),
    ],
}

# Sanity constants the tests assert against.
EXPECTED_MAIN_MODULE_COUNT = 5
# Legacy seeded 24 submodules; Phase 1 adds 3 for resources that had no legacy
# permission slot (category, emp_task, project_type) so they can be gated cleanly.
EXPECTED_SUBMODULE_COUNT = 27


@dataclass(frozen=True)
class RoleSeed:
    code: str
    name: str
    description: str
    # Main-module code -> actions granted on that module *and all of its
    # submodules*, unless overridden below.
    grants: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # Submodule code -> actions, overriding whatever the parent grant implied.
    overrides: dict[str, tuple[str, ...]] = field(default_factory=dict)
    grant_all: bool = False


DEFAULT_ROLES: list[RoleSeed] = [
    RoleSeed(
        code=SUPER_ADMIN_ROLE_CODE,
        name="Super Administrator",
        description="Unrestricted access to every module and action.",
        grant_all=True,
    ),
    RoleSeed(
        code="ADM",
        name="Administrator",
        description=(
            "Manages org structure, projects and people. Read-only on payroll "
            "and leave so that money and entitlement changes stay with their "
            "owning roles."
        ),
        grants={
            "administration": FULL,
            "humanres": FULL,
            "project": FULL,
            "payroll": VIEW_ONLY,
            "emp_leaves": VIEW_ONLY,
        },
    ),
    RoleSeed(
        code="HR",
        name="Human Resources Officer",
        description=(
            "Owns employee records, attendance and leave administration. "
            "Read-only on payroll configuration."
        ),
        grants={
            "humanres": FULL,
            "emp_leaves": FULL,
            "administration": VIEW_ONLY,
            "project": VIEW_ONLY,
            "payroll": NONE,
        },
        overrides={
            # HR maintains the shift definitions attendance is measured against.
            "shifts": FULL,
            "emp_settings": CONTRIBUTE,
        },
    ),
    RoleSeed(
        code="PAY",
        name="Payroll Officer",
        description=(
            "Owns payroll configuration, generation and reports. Needs to read "
            "employee and attendance data but must not alter it."
        ),
        grants={
            "payroll": FULL,
            "humanres": VIEW_ONLY,
            "emp_leaves": VIEW_ONLY,
            "administration": NONE,
            "project": NONE,
        },
    ),
    RoleSeed(
        code=DEFAULT_EMPLOYEE_ROLE_CODE,
        name="Employee (Self-Service)",
        description=(
            "Default role for rank-and-file accounts, matching the legacy 'SUR' "
            "code auto-assigned by ManpowerController. Can see their own "
            "records and file leave; cannot administer anything."
        ),
        grants={
            "project": NONE,
            "humanres": NONE,
            "administration": NONE,
            "payroll": NONE,
            "emp_leaves": NONE,
        },
        overrides={
            "daily_time_record": VIEW_ONLY,
            # Needs the Leave Administration nav heading visible to reach the
            # pages below it.
            "emp_leaves": VIEW_ONLY,
            "employee_leaves": VIEW_ONLY,
            "leave_request": ("view", "add"),
            "leave_calendar": VIEW_ONLY,
        },
    ),
]


def _actions_to_columns(actions: tuple[str, ...]) -> dict[str, bool]:
    granted = {PermissionAction(a) for a in actions}
    return {
        column: (action in granted) for action, column in ACTION_COLUMN.items()
    }


def _resolve_grants(seed: RoleSeed) -> dict[str, tuple[str, ...]]:
    """Flatten a RoleSeed into {module_code: actions} for all 29 modules."""
    resolved: dict[str, tuple[str, ...]] = {}

    for main_code, _ in MAIN_MODULES:
        main_actions = FULL if seed.grant_all else seed.grants.get(main_code, NONE)
        resolved[main_code] = main_actions
        for sub_code, _ in SUBMODULES[main_code]:
            resolved[sub_code] = main_actions

    if not seed.grant_all:
        for code, actions in seed.overrides.items():
            resolved[code] = actions

    return resolved


def seed_modules(*, session: Session) -> dict[str, Module]:
    """Insert any missing modules; return every module keyed by code."""
    existing = {m.code: m for m in session.exec(select(Module)).all()}

    for order, (code, name) in enumerate(MAIN_MODULES):
        if code not in existing:
            module = Module(code=code, name=name, parent_id=None, sort_order=order)
            session.add(module)
            existing[code] = module
    session.commit()
    for module in existing.values():
        session.refresh(module)

    order = 0
    for parent_code, children in SUBMODULES.items():
        parent = existing[parent_code]
        for code, name in children:
            if code not in existing:
                module = Module(
                    code=code, name=name, parent_id=parent.id, sort_order=order
                )
                session.add(module)
                existing[code] = module
            order += 1
    session.commit()
    for module in existing.values():
        session.refresh(module)

    return existing


def seed_roles(*, session: Session, modules: dict[str, Module]) -> dict[str, Role]:
    """Insert any missing roles and their permission rows."""
    existing = {r.code: r for r in session.exec(select(Role)).all()}

    for seed in DEFAULT_ROLES:
        if seed.code not in existing:
            role = Role(
                code=seed.code,
                name=seed.name,
                description=seed.description,
                is_system=True,
            )
            session.add(role)
            existing[seed.code] = role
    session.commit()
    for role in existing.values():
        session.refresh(role)

    for seed in DEFAULT_ROLES:
        role = existing[seed.code]
        current = {
            permission.module_id: permission
            for permission in session.exec(
                select(RolePermission).where(RolePermission.role_id == role.id)
            ).all()
        }
        for module_code, actions in _resolve_grants(seed).items():
            module = modules[module_code]
            if module.id in current:
                continue
            session.add(
                RolePermission(
                    role_id=role.id,
                    module_id=module.id,
                    **_actions_to_columns(actions),
                )
            )
    session.commit()

    return existing


def seed_rbac(*, session: Session) -> None:
    """Idempotently seed modules, submodules and default roles."""
    modules = seed_modules(session=session)
    seed_roles(session=session, modules=modules)
