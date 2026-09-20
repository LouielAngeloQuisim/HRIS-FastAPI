#!/usr/bin/env python
# B7 — Payroll generation load-test threshold checker.
#
# Verifies that generating payroll for 100 employees completes within the
# allowed wall-clock budget (default: 5 seconds per the plan §8).
#
# Usage:
#     python scripts/migration/load_test_thresholds.py \
#         --pg-url postgresql://postgres:postgres123@localhost:5432/app \
#         --employees 100 --threshold-seconds 5
from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from sqlmodel import Session, create_engine

from app.employee.models import EmployeeRecords, EmployeeStatus
from app.payroll.models import CutoffType, EmployeeSalary
from app.payroll.services import generate_payroll


def _seed_employees(session: Session, count: int) -> None:
    for i in range(count):
        emp = EmployeeRecords(
            id=uuid.uuid4(),
            employee_code=f"LOAD-{i:04d}",
            first_name=f"Load{i}",
            last_name="Test",
            birthdate=date(1990, 1, 1),
            employment_type="regular",
            employee_status=EmployeeStatus.ACTIVE,
            date_hired=date(2020, 1, 1),
            is_deleted=False,
        )
        session.add(emp)
        session.add(
            EmployeeSalary(
                id=uuid.uuid4(),
                employee_id=emp.id,
                basic_rate=25000,
                currency="PHP",
                effective_date=date(2020, 1, 1),
                pay_type="monthly",
                overtime_rate=1.25,
                absent_penalty_rate=1.0,
                non_taxable_allowance=0,
                is_active=True,
                is_deleted=False,
            )
        )
    session.commit()


def run_load_test(args: argparse.Namespace) -> int:
    engine = create_engine(args.pg_url, pool_pre_ping=True)
    with Session(engine) as session:
        sys.stdout.write(f"[load] Seeding {args.employees} employees...\n")
        _seed_employees(session, args.employees)

        sys.stdout.write(f"[load] Running payroll generation for {args.employees} employees...\n")
        start = time.perf_counter()
        try:
            generate_payroll(
                session=session,
                cutoff_type=CutoffType.MONTHLY.value,
                date_from=date(2026, 9, 1),
                date_to=date(2026, 9, 30),
                created_by=None,
            )
        except Exception as exc:
            sys.stdout.write(f"[load] Generation failed: {exc}\n")
            return 1
        elapsed = time.perf_counter() - start
        sys.stdout.write(f"[load] Elapsed: {elapsed:.3f}s (threshold: {args.threshold_seconds}s)\n")

        if elapsed <= args.threshold_seconds:
            sys.stdout.write("[load] PASS\n")
            return 0
        else:
            sys.stdout.write(f"[load] FAIL: {elapsed:.3f}s exceeds {args.threshold_seconds}s threshold\n")
            return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Payroll load-test threshold checker")
    parser.add_argument("--pg-url", required=True)
    parser.add_argument("--employees", type=int, default=100)
    parser.add_argument("--threshold-seconds", type=float, default=5.0)
    args = parser.parse_args()
    return run_load_test(args)


if __name__ == "__main__":
    import uuid  # noqa: E402
    sys.exit(main())
