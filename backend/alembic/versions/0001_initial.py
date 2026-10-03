"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remind_days_before", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "debts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("principal", sa.Numeric(14, 2), nullable=False),
        sa.Column("annual_rate", sa.Numeric(6, 3), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("first_payment_date", sa.Date(), nullable=False),
        sa.Column("schedule_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_debts_user_id", "debts", ["user_id"])

    op.create_table(
        "early_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("debt_id", sa.Integer(), sa.ForeignKey("debts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_early_payments_debt_id", "early_payments", ["debt_id"])

    op.create_table(
        "paid_periods",
        sa.Column("debt_id", sa.Integer(), sa.ForeignKey("debts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("period_no", sa.Integer(), primary_key=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("paid_periods")
    op.drop_table("early_payments")
    op.drop_table("debts")
    op.drop_table("users")
