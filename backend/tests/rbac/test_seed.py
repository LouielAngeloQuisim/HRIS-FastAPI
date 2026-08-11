"""Phase 0 / Item 5 - modules, submodules and role-code seed.

The module and submodule sets are asserted against the legacy source verbatim
(MainModules.php / SubModules.php), so drift from the system being replaced is
caught rather than assumed.
"""

from sqlmodel import Session, func, select

from app.rbac.models import Module, PermissionAction, Role, RolePermission
from app.rbac.seed import (
    DEFAULT_EMPLOYEE_ROLE_CODE,
    DEFAULT_ROLES,
    EXPECTED_MAIN_MODULE_COUNT,
    EXPECTED_SUBMODULE_COUNT,
    LEGACY_SUBMODULE_CODE_MAP,
    MAIN_MODULES,
    SUBMODULES,
    SUPER_ADMIN_ROLE_CODE,
    seed_rbac,
)
from app.rbac.selectors import get_module_by_code, get_role_by_code
from app.rbac.services import user_has_permission
from app.user.models import User, UserCreate
from app.user.services import create_user
from tests.utils.utils import random_email, random_lower_string

# Verbatim from src/Entity/MainModules.php - the five array columns.
LEGACY_MAIN_MODULES = {
    "project",
    "humanres",
    "administration",
    "payroll",
    "emp_leaves",
}

# Verbatim from src/Entity/SubModules.php - the 24 array columns, plus the 3
# Phase 1 submodules added because they had no legacy permission slot.
LEGACY_SUBMODULES = {
    "daily_time_record",
    "subdivision",
    "division",
    "department",
    "phase",
    "owner",
    "models",
    "model_types",
    "emp_settings",
    "shifts",
    "projects",
    "emp_project",
    "emp_list",
    "sss_config",
    "pagibig_config",
    "bir_config",
    "philhealth_config",
    "payroll",
    "payroll_reports",
    "leave_policy",
    "emp_leaves",
    "holiday_config",
    "leave_request",
    "leave_calendar",
    # Phase 1 additions (no legacy permission concept existed):
    "project_type",
    "category",
    "emp_task",
}

# What those 24 legacy codes become after the documented collision mapping.
EXPECTED_SUBMODULE_CODES = {
    LEGACY_SUBMODULE_CODE_MAP.get(code, code) for code in LEGACY_SUBMODULES
}


class TestModuleSeedMatchesLegacy:
    def test_main_modules_match_legacy_exactly(self, db: Session) -> None:
        seeded = {
            m.code
            for m in db.exec(
                select(Module).where(Module.parent_id.is_(None))  # type: ignore[union-attr]
            ).all()
        }
        assert seeded == LEGACY_MAIN_MODULES

    def test_there_are_five_main_modules(self, db: Session) -> None:
        count = db.exec(
            select(func.count())
            .select_from(Module)
            .where(Module.parent_id.is_(None))  # type: ignore[union-attr]
        ).one()
        assert count == EXPECTED_MAIN_MODULE_COUNT

    def test_submodules_match_legacy_exactly(self, db: Session) -> None:
        seeded = {
            m.code
            for m in db.exec(
                select(Module).where(Module.parent_id.is_not(None))  # type: ignore[union-attr]
            ).all()
        }
        assert seeded == EXPECTED_SUBMODULE_CODES

    def test_collision_mapping_is_applied(self, db: Session) -> None:
        """`payroll` and `emp_leaves` exist as main modules AND legacy submodules.

        The main module must keep the legacy code, and the renamed submodule
        must exist alongside it under the right parent.
        """
        for legacy_code, new_code in LEGACY_SUBMODULE_CODE_MAP.items():
            main = get_module_by_code(session=db, code=legacy_code)
            assert main is not None, legacy_code
            assert main.parent_id is None, (
                f"{legacy_code} should be the main module"
            )

            sub = get_module_by_code(session=db, code=new_code)
            assert sub is not None, new_code
            assert sub.parent_id == main.id, (
                f"{new_code} should be a submodule of {legacy_code}"
            )

    def test_every_legacy_submodule_is_reachable(self, db: Session) -> None:
        """No legacy permission concept is silently dropped by the rename."""
        for legacy_code in LEGACY_SUBMODULES:
            resolved = LEGACY_SUBMODULE_CODE_MAP.get(legacy_code, legacy_code)
            assert get_module_by_code(session=db, code=resolved) is not None, (
                f"legacy submodule {legacy_code} has no counterpart"
            )

    def test_there_are_twenty_four_submodules(self, db: Session) -> None:
        count = db.exec(
            select(func.count())
            .select_from(Module)
            .where(Module.parent_id.is_not(None))  # type: ignore[union-attr]
        ).one()
        assert count == EXPECTED_SUBMODULE_COUNT

    def test_no_submodule_is_orphaned(self, db: Session) -> None:
        main_ids = {
            m.id
            for m in db.exec(
                select(Module).where(Module.parent_id.is_(None))  # type: ignore[union-attr]
            ).all()
        }
        for module in db.exec(
            select(Module).where(Module.parent_id.is_not(None))  # type: ignore[union-attr]
        ).all():
            assert module.parent_id in main_ids, module.code

    def test_module_codes_are_unique(self, db: Session) -> None:
        codes = [m.code for m in db.exec(select(Module)).all()]
        assert len(codes) == len(set(codes))

    def test_submodule_map_covers_every_main_module(self) -> None:
        assert set(SUBMODULES) == {code for code, _ in MAIN_MODULES}

    def test_submodule_map_has_no_duplicates_across_parents(self) -> None:
        flat = [code for children in SUBMODULES.values() for code, _ in children]
        assert len(flat) == len(set(flat)) == EXPECTED_SUBMODULE_COUNT


class TestRoleSeed:
    def test_all_default_roles_exist(self, db: Session) -> None:
        for seed in DEFAULT_ROLES:
            role = get_role_by_code(session=db, code=seed.code)
            assert role is not None, seed.code
            assert role.is_system is True

    def test_role_codes_are_unique(self) -> None:
        codes = [seed.code for seed in DEFAULT_ROLES]
        assert len(codes) == len(set(codes))

    def test_legacy_employee_role_code_is_present(self, db: Session) -> None:
        """`SUR` is the one code hardcoded in the legacy source."""
        assert get_role_by_code(session=db, code=DEFAULT_EMPLOYEE_ROLE_CODE)

    def test_every_role_has_a_permission_row_per_module(self, db: Session) -> None:
        module_count = db.exec(select(func.count()).select_from(Module)).one()
        for seed in DEFAULT_ROLES:
            role = get_role_by_code(session=db, code=seed.code)
            assert role is not None
            rows = db.exec(
                select(func.count())
                .select_from(RolePermission)
                .where(RolePermission.role_id == role.id)
            ).one()
            assert rows == module_count, (
                f"{seed.code} has {rows} permission rows, expected {module_count}"
            )

    def test_super_admin_can_do_everything(self, db: Session) -> None:
        role = get_role_by_code(session=db, code=SUPER_ADMIN_ROLE_CODE)
        assert role is not None
        rows = db.exec(
            select(RolePermission).where(RolePermission.role_id == role.id)
        ).all()
        assert rows
        for row in rows:
            assert row.can_view and row.can_add and row.can_edit and row.can_delete

    def test_employee_role_is_genuinely_low_privilege(self, db: Session) -> None:
        """Guards against the seed accidentally over-granting the default role."""
        role = get_role_by_code(session=db, code=DEFAULT_EMPLOYEE_ROLE_CODE)
        assert role is not None
        rows = db.exec(
            select(RolePermission).where(RolePermission.role_id == role.id)
        ).all()
        assert not any(row.can_delete for row in rows), "employee role can delete"
        assert not any(row.can_edit for row in rows), "employee role can edit"


class TestSeededRolesDriveTheDependency:
    """The seed and require_permission must agree."""

    def _user_with_role(self, db: Session, code: str) -> User:
        role = get_role_by_code(session=db, code=code)
        assert role is not None
        user = create_user(
            session=db,
            user_create=UserCreate(
                email=random_email(), password=random_lower_string()
            ),
        )
        user.role_id = role.id
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def test_payroll_officer_can_edit_payroll(self, db: Session) -> None:
        user = self._user_with_role(db, "PAY")
        assert user_has_permission(
            session=db, user=user, module_code="payroll", action=PermissionAction.EDIT
        )

    def test_payroll_officer_cannot_edit_administration(self, db: Session) -> None:
        user = self._user_with_role(db, "PAY")
        assert not user_has_permission(
            session=db,
            user=user,
            module_code="division",
            action=PermissionAction.EDIT,
        )

    def test_hr_officer_can_manage_shifts(self, db: Session) -> None:
        """Explicit submodule override on top of a view-only parent grant."""
        user = self._user_with_role(db, "HR")
        assert user_has_permission(
            session=db, user=user, module_code="shifts", action=PermissionAction.EDIT
        )

    def test_hr_officer_cannot_delete_departments(self, db: Session) -> None:
        user = self._user_with_role(db, "HR")
        assert not user_has_permission(
            session=db,
            user=user,
            module_code="department",
            action=PermissionAction.DELETE,
        )

    def test_employee_can_file_a_leave_request(self, db: Session) -> None:
        user = self._user_with_role(db, DEFAULT_EMPLOYEE_ROLE_CODE)
        assert user_has_permission(
            session=db,
            user=user,
            module_code="leave_request",
            action=PermissionAction.ADD,
        )

    def test_employee_cannot_touch_payroll(self, db: Session) -> None:
        user = self._user_with_role(db, DEFAULT_EMPLOYEE_ROLE_CODE)
        for action in PermissionAction:
            assert not user_has_permission(
                session=db, user=user, module_code="payroll", action=action
            ), action


class TestSeedIdempotency:
    def test_reseeding_creates_no_duplicates(self, db: Session) -> None:
        """init_db runs on every startup, so this must be safe to repeat."""
        before_modules = db.exec(select(func.count()).select_from(Module)).one()
        before_roles = db.exec(select(func.count()).select_from(Role)).one()
        before_perms = db.exec(
            select(func.count()).select_from(RolePermission)
        ).one()

        seed_rbac(session=db)
        seed_rbac(session=db)

        assert db.exec(select(func.count()).select_from(Module)).one() == before_modules
        assert db.exec(select(func.count()).select_from(Role)).one() == before_roles
        assert (
            db.exec(select(func.count()).select_from(RolePermission)).one()
            == before_perms
        )


class TestBootstrapSuperuser:
    def test_first_superuser_is_bound_to_the_super_admin_role(
        self, db: Session
    ) -> None:
        from app.config.settings import settings

        user = db.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).first()
        role = get_role_by_code(session=db, code=SUPER_ADMIN_ROLE_CODE)

        assert user is not None
        assert role is not None
        assert user.role_id == role.id
