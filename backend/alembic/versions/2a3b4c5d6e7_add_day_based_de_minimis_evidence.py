"""Add evidence and limits for day-based de minimis benefits.

Revision ID: 2a3b4c5d6e7f
Revises: 3c4d5e6f7a8b
Create Date: 2026-10-09
"""

from alembic import op
import sqlalchemy as sa

revision = "2a3b4c5d6e7f"
down_revision = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_ledger_payroll_tax_benefit_reference",
        "leave_ledger_entry",
        ["reference"],
        unique=True,
        postgresql_where=sa.text(
            "reference LIKE 'PayrollTaxBenefit:%' OR "
            "reference LIKE 'PayrollTaxBenefitReversal:%'"
        ),
    )
    op.add_column(
        "leave_policy",
        sa.Column(
            "tax_exempt_unused_vacation_leave",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "employee_tax_benefit", sa.Column("qualifying_days", sa.Integer(), nullable=True)
    )
    op.add_column(
        "employee_tax_benefit",
        sa.Column("regional_daily_minimum_wage", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "employee_tax_benefit", sa.Column("region_code", sa.String(32), nullable=True)
    )
    op.add_column(
        "employee_tax_benefit",
        sa.Column("wage_order_reference", sa.String(512), nullable=True),
    )
    op.add_column(
        "employee_tax_benefit",
        sa.Column("qualifying_work_dates", sa.JSON(), nullable=True),
    )
    op.add_column(
        "employee_tax_benefit",
        sa.Column("wage_order_effective_from", sa.Date(), nullable=True),
    )
    op.add_column(
        "employee_tax_benefit",
        sa.Column("wage_order_effective_to", sa.Date(), nullable=True),
    )
    op.add_column(
        "employee_tax_benefit",
        sa.Column("vacation_leave_policy_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "employee_tax_benefit",
        sa.Column("eligibility_snapshot", sa.JSON(), nullable=True),
    )
    op.create_foreign_key(
        "fk_employee_tax_benefit_vacation_leave_policy",
        "employee_tax_benefit",
        "leave_policy",
        ["vacation_leave_policy_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "employee_tax_year_declaration",
        sa.Column("opening_unused_vacation_leave_days_ytd", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_employee_tax_unused_vacation_days_ytd",
        "employee_tax_year_declaration",
        "opening_unused_vacation_leave_days_ytd IS NULL OR "
        "opening_unused_vacation_leave_days_ytd BETWEEN 0 AND 12",
    )
    op.drop_constraint(
        "ck_employee_tax_benefit_classification", "employee_tax_benefit", type_="check"
    )
    op.create_check_constraint(
        "ck_employee_tax_benefit_classification",
        "employee_tax_benefit",
        "(benefit_type IN ('thirteenth_month', 'other_benefit') AND de_minimis_category IS NULL) OR "
        "(benefit_type = 'de_minimis' AND de_minimis_category IN "
        "('medical_cash_dependents', 'rice_subsidy', 'uniform_clothing', "
        "'actual_medical_assistance', 'laundry_allowance', 'achievement_award', "
        "'christmas_anniversary_gift', 'cba_productivity_incentive', "
        "'daily_meal_ot_night', 'monetized_unused_vacation_leave'))",
    )
    op.create_check_constraint(
        "ck_employee_tax_benefit_day_evidence_shape",
        "employee_tax_benefit",
        "(de_minimis_category = 'daily_meal_ot_night' AND qualifying_days IS NOT NULL "
        "AND qualifying_days BETWEEN 1 AND 366 AND regional_daily_minimum_wage IS NOT NULL "
        "AND regional_daily_minimum_wage > 0 AND region_code IS NOT NULL "
        "AND length(trim(region_code)) > 0 AND wage_order_reference IS NOT NULL "
        "AND length(trim(wage_order_reference)) > 0 AND qualifying_work_dates IS NOT NULL "
        "AND wage_order_effective_from IS NOT NULL AND "
        "(wage_order_effective_to IS NULL OR wage_order_effective_to >= wage_order_effective_from) "
        "AND vacation_leave_policy_id IS NULL) OR "
        "(de_minimis_category = 'monetized_unused_vacation_leave' AND qualifying_days IS NOT NULL "
        "AND qualifying_days BETWEEN 1 AND 366 "
        "AND regional_daily_minimum_wage IS NULL AND region_code IS NULL AND wage_order_reference IS NULL "
        "AND qualifying_work_dates IS NULL AND wage_order_effective_from IS NULL "
        "AND wage_order_effective_to IS NULL AND vacation_leave_policy_id IS NOT NULL) OR "
        "(de_minimis_category NOT IN ('daily_meal_ot_night', 'monetized_unused_vacation_leave') "
        "AND qualifying_days IS NULL AND regional_daily_minimum_wage IS NULL "
        "AND region_code IS NULL AND wage_order_reference IS NULL AND qualifying_work_dates IS NULL "
        "AND wage_order_effective_from IS NULL AND wage_order_effective_to IS NULL "
        "AND vacation_leave_policy_id IS NULL) OR "
        "(de_minimis_category IS NULL AND qualifying_days IS NULL AND regional_daily_minimum_wage IS NULL "
        "AND region_code IS NULL AND wage_order_reference IS NULL AND qualifying_work_dates IS NULL "
        "AND wage_order_effective_from IS NULL AND wage_order_effective_to IS NULL "
        "AND vacation_leave_policy_id IS NULL)",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(
        sa.text(
            "SELECT 1 FROM employee_tax_benefit WHERE "
            "de_minimis_category IN ('daily_meal_ot_night', 'monetized_unused_vacation_leave') "
            "OR qualifying_days IS NOT NULL OR regional_daily_minimum_wage IS NOT NULL "
            "OR region_code IS NOT NULL OR wage_order_reference IS NOT NULL "
            "OR qualifying_work_dates IS NOT NULL OR wage_order_effective_from IS NOT NULL "
            "OR wage_order_effective_to IS NOT NULL OR vacation_leave_policy_id IS NOT NULL "
            "OR eligibility_snapshot IS NOT NULL LIMIT 1"
        )
    ).first() or bind.execute(
        sa.text(
            "SELECT 1 FROM employee_tax_year_declaration "
            "WHERE opening_unused_vacation_leave_days_ytd IS NOT NULL LIMIT 1"
        )
    ).first() or bind.execute(
        sa.text("SELECT 1 FROM leave_policy WHERE tax_exempt_unused_vacation_leave LIMIT 1")
    ).first():
        raise RuntimeError(
            "Cannot remove day-based de minimis evidence; preserve payroll tax records and use a forward migration."
        )
    if bind.execute(
        sa.text(
            "SELECT 1 FROM leave_ledger_entry WHERE "
            "reference LIKE 'PayrollTaxBenefit:%' OR "
            "reference LIKE 'PayrollTaxBenefitReversal:%' LIMIT 1"
        )
    ).first():
        raise RuntimeError(
            "Cannot remove payroll-benefit leave-ledger identity protection while benefit records exist."
        )
    op.drop_index(
        "uq_ledger_payroll_tax_benefit_reference", table_name="leave_ledger_entry"
    )
    op.drop_constraint(
        "ck_employee_tax_benefit_day_evidence_shape",
        "employee_tax_benefit",
        type_="check",
    )
    op.drop_constraint(
        "ck_employee_tax_benefit_classification",
        "employee_tax_benefit",
        type_="check",
    )
    op.drop_constraint(
        "ck_employee_tax_unused_vacation_days_ytd",
        "employee_tax_year_declaration",
        type_="check",
    )
    op.drop_constraint(
        "fk_employee_tax_benefit_vacation_leave_policy",
        "employee_tax_benefit",
        type_="foreignkey",
    )
    op.drop_column("leave_policy", "tax_exempt_unused_vacation_leave")
    op.drop_column("employee_tax_benefit", "eligibility_snapshot")
    op.drop_column("employee_tax_benefit", "vacation_leave_policy_id")
    op.create_check_constraint(
        "ck_employee_tax_benefit_classification",
        "employee_tax_benefit",
        "(benefit_type IN ('thirteenth_month', 'other_benefit') AND de_minimis_category IS NULL) OR "
        "(benefit_type = 'de_minimis' AND de_minimis_category IN "
        "('medical_cash_dependents', 'rice_subsidy', 'uniform_clothing', "
        "'actual_medical_assistance', 'laundry_allowance', 'achievement_award', "
        "'christmas_anniversary_gift', 'cba_productivity_incentive'))",
    )
    op.drop_column("employee_tax_year_declaration", "opening_unused_vacation_leave_days_ytd")
    for column in (
        "wage_order_reference",
        "wage_order_effective_to",
        "wage_order_effective_from",
        "qualifying_work_dates",
        "region_code",
        "regional_daily_minimum_wage",
        "qualifying_days",
    ):
        op.drop_column("employee_tax_benefit", column)
