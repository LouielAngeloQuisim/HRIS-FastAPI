"""add leave_policy, enrollment, request, ledger, holiday tables (Phase b3)

Revision ID: b9748b3e7b5c
Revises: c085a769992a
Create Date: 2026-09-02 08:05:00.000000
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = 'b9748b3e7b5c'
down_revision = 'c085a769992a'
branch_labels = None
depends_on = None


def upgrade():
    # --- leave_policy ---
    op.create_table('leave_policy',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
    sa.Column('calendar_color', sqlmodel.sql.sqltypes.AutoString(length=7), nullable=False),
    sa.Column('cadence', sa.Enum('annual', 'monthly', name='leavecadence'), nullable=False),
    sa.Column('annual_entitlement_days', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('prorate_on_hire', sa.Boolean(), nullable=False),
    sa.Column('carry_over_enabled', sa.Boolean(), nullable=False),
    sa.Column('carry_over_max_days', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('carry_over_expires_on', sa.Date(), nullable=True),
    sa.Column('is_paid', sa.Boolean(), nullable=False),
    sa.Column('eligible_departments', sa.JSON(), nullable=False),
    sa.Column('gender_scope', sa.Enum('all', 'male', 'female', name='genderscope'), nullable=False),
    sa.Column('marital_status_scope', sa.Enum('all', 'single', 'married', 'widowed', 'divorced', name='maritalstatusscope'), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_system', sa.Boolean(), nullable=False),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_leave_policy_code'),
    )
    op.create_index('ix_leave_policy_code', 'leave_policy', ['code'], unique=True)
    op.create_index('ix_leave_policy_is_active', 'leave_policy', ['is_active'], unique=False)

    # --- employee_leave_enrollment ---
    op.create_table('employee_leave_enrollment',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('employee_id', sa.Uuid(), nullable=True),
    sa.Column('policy_id', sa.Uuid(), nullable=True),
    sa.Column('leave_year', sa.Integer(), nullable=False),
    sa.Column('granted_days', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_transferred', sa.Boolean(), nullable=False),
    sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['employee_id'], ['employee_records.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['policy_id'], ['leave_policy.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('employee_id', 'policy_id', 'leave_year', name='uq_enrollment_employee_policy_year'),
    )
    op.create_index('ix_enrollment_employee_deleted', 'employee_leave_enrollment', ['employee_id', 'is_deleted'], unique=False)
    op.create_index('ix_enrollment_policy_deleted', 'employee_leave_enrollment', ['policy_id', 'is_deleted'], unique=False)
    op.create_index('ix_employee_leave_enrollment_employee_id', 'employee_leave_enrollment', ['employee_id'], unique=False)
    op.create_index('ix_employee_leave_enrollment_policy_id', 'employee_leave_enrollment', ['policy_id'], unique=False)
    op.create_index('ix_employee_leave_enrollment_leave_year', 'employee_leave_enrollment', ['leave_year'], unique=False)

    # --- leave_request ---
    op.create_table('leave_request',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('employee_id', sa.Uuid(), nullable=True),
    sa.Column('policy_id', sa.Uuid(), nullable=True),
    sa.Column('enrollment_id', sa.Uuid(), nullable=True),
    sa.Column('date_start', sa.Date(), nullable=False),
    sa.Column('date_end', sa.Date(), nullable=False),
    sa.Column('leave_year', sa.Integer(), nullable=False),
    sa.Column('requested_hours', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('total_days_requested', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
    sa.Column('document_ref', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'cancelled', name='leavestatus'), nullable=False),
    sa.Column('created_by_user', sa.Uuid(), nullable=True),
    sa.Column('approved_by_user', sa.Uuid(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejected_by_user', sa.Uuid(), nullable=True),
    sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_by_user', sa.Uuid(), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_note', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['employee_id'], ['employee_records.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['policy_id'], ['leave_policy.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['enrollment_id'], ['employee_leave_enrollment.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_user'], ['user.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['approved_by_user'], ['user.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['rejected_by_user'], ['user.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['cancelled_by_user'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_leave_request_employee_deleted', 'leave_request', ['employee_id', 'is_deleted'], unique=False)
    op.create_index('ix_leave_request_status_deleted', 'leave_request', ['status', 'is_deleted'], unique=False)
    op.create_index('ix_leave_request_status_year', 'leave_request', ['status', 'leave_year'], unique=False)
    op.create_index('ix_leave_request_employee_id', 'leave_request', ['employee_id'], unique=False)
    op.create_index('ix_leave_request_policy_id', 'leave_request', ['policy_id'], unique=False)
    op.create_index('ix_leave_request_enrollment_id', 'leave_request', ['enrollment_id'], unique=False)
    op.create_index('ix_leave_request_leave_year', 'leave_request', ['leave_year'], unique=False)
    op.create_index('ix_leave_request_created_by_user', 'leave_request', ['created_by_user'], unique=False)

    # --- leave_request_event ---
    op.create_table('leave_request_event',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('request_id', sa.Uuid(), nullable=False),
    sa.Column('event', sa.Enum('created', 'approved', 'rejected', 'cancelled', 'noop', name='leaverequesteventtype'), nullable=False),
    sa.Column('actor_user_id', sa.Uuid(), nullable=True),
    sa.Column('at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('note', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
    sa.Column('run_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['request_id'], ['leave_request.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['actor_user_id'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_leave_event_request', 'leave_request_event', ['request_id'], unique=False)
    op.create_index('ix_leave_event_actor', 'leave_request_event', ['actor_user_id'], unique=False)

    # --- leave_ledger_entry ---
    op.create_table('leave_ledger_entry',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('employee_id', sa.Uuid(), nullable=False),
    sa.Column('policy_id', sa.Uuid(), nullable=False),
    sa.Column('enrollment_id', sa.Uuid(), nullable=True),
    sa.Column('leave_year', sa.Integer(), nullable=False),
    sa.Column('source', sa.Enum('grant', 'accrual', 'carryover_in', 'consumed', 'reversal', 'carryover_out', 'manual_adjustment', name='leaveledgersource'), nullable=False),
    sa.Column('amount', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('reference', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
    sa.Column('original_year', sa.Integer(), nullable=True),
    sa.Column('note', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
    sa.Column('actor_user_id', sa.Uuid(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['employee_id'], ['employee_records.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['policy_id'], ['leave_policy.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['enrollment_id'], ['employee_leave_enrollment.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['actor_user_id'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ledger_employee_policy_year', 'leave_ledger_entry', ['employee_id', 'policy_id', 'leave_year'], unique=False)
    op.create_index('ix_ledger_source', 'leave_ledger_entry', ['source'], unique=False)
    op.create_index('ix_leave_ledger_entry_employee_id', 'leave_ledger_entry', ['employee_id'], unique=False)
    op.create_index('ix_leave_ledger_entry_policy_id', 'leave_ledger_entry', ['policy_id'], unique=False)
    op.create_index('ix_leave_ledger_entry_leave_year', 'leave_ledger_entry', ['leave_year'], unique=False)

    # --- holiday_config ---
    op.create_table('holiday_config',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('month_day', sqlmodel.sql.sqltypes.AutoString(length=5), nullable=False),
    sa.Column('type', sa.Enum('regular', 'special_non_working', 'special_working', 'company', name='holidaytype'), nullable=False),
    sa.Column('region_code', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
    sa.Column('observe_weekend_as', sa.Enum('previous_friday', 'next_monday', 'nearest_weekday', name='observeweekendas'), nullable=True),
    sa.Column('multiplier_regular', sa.Numeric(precision=6, scale=3), nullable=True),
    sa.Column('multiplier_overtime', sa.Numeric(precision=6, scale=3), nullable=True),
    sa.Column('is_recurring', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_holiday_config_code'),
    )
    op.create_index('ix_holiday_config_code', 'holiday_config', ['code'], unique=True)
    op.create_index('ix_holiday_config_is_active', 'holiday_config', ['is_active'], unique=False)

    # --- holiday_instance ---
    op.create_table('holiday_instance',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('config_id', sa.Uuid(), nullable=False),
    sa.Column('observed_date', sa.Date(), nullable=False),
    sa.Column('raw_date', sa.Date(), nullable=True),
    sa.Column('leave_year', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['config_id'], ['holiday_config.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('config_id', 'observed_date', name='uq_holiday_instance_config_date'),
    )
    op.create_index('ix_holiday_instance_year', 'holiday_instance', ['leave_year'], unique=False)
    op.create_index('ix_holiday_instance_date', 'holiday_instance', ['observed_date'], unique=False)
    op.create_index('ix_holiday_instance_config_id', 'holiday_instance', ['config_id'], unique=False)

def downgrade():
    op.drop_table('holiday_instance')
    op.drop_table('holiday_config')
    op.drop_table('leave_ledger_entry')
    op.drop_table('leave_request_event')
    op.drop_table('leave_request')
    op.drop_table('employee_leave_enrollment')
    op.drop_table('leave_policy')
