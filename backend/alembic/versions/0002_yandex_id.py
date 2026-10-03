"""yandex id auth instead of telegram

Пользователи теперь входят через Яндекс ID, Telegram-бот удалён. Существующие данные,
привязанные к Telegram-аккаунтам, не переносятся — таблицы очищаются.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _clear_data() -> None:
    for table in ("paid_periods", "early_payments", "debts", "users"):
        op.execute(sa.text(f"DELETE FROM {table}"))


def upgrade() -> None:
    _clear_data()
    op.drop_index("ix_users_telegram_id", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("telegram_id")
        batch.drop_column("first_name")
        batch.drop_column("username")
        batch.drop_column("reminders_enabled")
        batch.drop_column("remind_days_before")
        batch.add_column(sa.Column("yandex_id", sa.String(64), nullable=False))
        batch.add_column(sa.Column("login", sa.String(255), nullable=False))
        batch.add_column(sa.Column("display_name", sa.String(255), nullable=False))
        batch.add_column(sa.Column("email", sa.String(255), nullable=True))
        batch.add_column(sa.Column("avatar_id", sa.String(255), nullable=True))
    op.create_index("ix_users_yandex_id", "users", ["yandex_id"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])


def downgrade() -> None:
    op.drop_table("sessions")
    _clear_data()
    op.drop_index("ix_users_yandex_id", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("avatar_id")
        batch.drop_column("email")
        batch.drop_column("display_name")
        batch.drop_column("login")
        batch.drop_column("yandex_id")
        batch.add_column(sa.Column("telegram_id", sa.BigInteger(), nullable=False))
        batch.add_column(sa.Column("first_name", sa.String(255), nullable=False))
        batch.add_column(sa.Column("username", sa.String(255), nullable=True))
        batch.add_column(sa.Column("reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("remind_days_before", sa.Integer(), nullable=False, server_default="3"))
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)
