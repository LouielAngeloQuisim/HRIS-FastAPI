"""Payroll roster snapshots serialize with employee and assignment changes."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep

from sqlmodel import Session

from app.config.database import engine
from app.payroll.roster_lock import lock_payroll_roster


def test_roster_lock_blocks_a_concurrent_roster_writer_until_snapshot_finishes() -> None:
    first_locked = Event()
    second_started = Event()

    with Session(engine) as snapshot_session:
        lock_payroll_roster(snapshot_session)
        first_locked.set()

        def roster_writer() -> None:
            assert first_locked.wait(timeout=5)
            with Session(engine) as writer_session:
                second_started.set()
                lock_payroll_roster(writer_session)
                writer_session.commit()

        with ThreadPoolExecutor(max_workers=1) as executor:
            writer = executor.submit(roster_writer)
            assert second_started.wait(timeout=5)
            sleep(0.1)
            assert not writer.done(), "writer bypassed the payroll roster transaction lock"
            snapshot_session.commit()
            writer.result(timeout=5)
