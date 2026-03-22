"""add clawmarket marketplace tables and columns

Revision ID: b9c8d7e6f5a4
Revises: a9b1c2d3e4f7
Create Date: 2026-03-22 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "b9c8d7e6f5a4"
down_revision = "a9b1c2d3e4f7"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_key_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_columns = _column_names(inspector, "users")
    if "account_role" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "account_role",
                sa.String(),
                nullable=False,
                server_default="requester",
            ),
        )
    if "company_name" not in user_columns:
        op.add_column("users", sa.Column("company_name", sa.String(), nullable=True))
    if "wechat_handle" not in user_columns:
        op.add_column("users", sa.Column("wechat_handle", sa.String(), nullable=True))
    inspector = sa.inspect(bind)
    if "ix_users_account_role" not in _index_names(inspector, "users"):
        op.create_index("ix_users_account_role", "users", ["account_role"], unique=False)

    agent_columns = _column_names(inspector, "agents")
    if "owner_id" not in agent_columns:
        op.add_column("agents", sa.Column("owner_id", sa.Uuid(), nullable=True))
    if "gateway_url" not in agent_columns:
        op.add_column("agents", sa.Column("gateway_url", sa.String(), nullable=True))
    if "skills" not in agent_columns:
        op.add_column("agents", sa.Column("skills", sa.JSON(), nullable=True))
    if "pricing" not in agent_columns:
        op.add_column("agents", sa.Column("pricing", sa.JSON(), nullable=True))
    if "availability" not in agent_columns:
        op.add_column("agents", sa.Column("availability", sa.JSON(), nullable=True))
    if "skill_tags" not in agent_columns:
        op.add_column("agents", sa.Column("skill_tags", sa.JSON(), nullable=True))
    if "max_concurrency" not in agent_columns:
        op.add_column(
            "agents",
            sa.Column("max_concurrency", sa.Integer(), nullable=False, server_default="1"),
        )
    if "score" not in agent_columns:
        op.add_column(
            "agents",
            sa.Column("score", sa.Float(), nullable=False, server_default="80"),
        )
    if "marketplace_enabled" not in agent_columns:
        op.add_column(
            "agents",
            sa.Column(
                "marketplace_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    inspector = sa.inspect(bind)
    if "ix_agents_owner_id" not in _index_names(inspector, "agents"):
        op.create_index("ix_agents_owner_id", "agents", ["owner_id"], unique=False)
    if "ix_agents_marketplace_enabled" not in _index_names(inspector, "agents"):
        op.create_index(
            "ix_agents_marketplace_enabled",
            "agents",
            ["marketplace_enabled"],
            unique=False,
        )
    if "fk_agents_owner_id_users" not in _foreign_key_names(inspector, "agents"):
        op.create_foreign_key(
            "fk_agents_owner_id_users",
            "agents",
            "users",
            ["owner_id"],
            ["id"],
        )

    task_columns = _column_names(inspector, "tasks")
    if "marketplace_state" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_state", sa.String(), nullable=True))
    if "marketplace_task_type" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_task_type", sa.String(), nullable=True))
    if "marketplace_budget_amount" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_budget_amount", sa.Integer(), nullable=True))
    if "marketplace_budget_currency" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_budget_currency", sa.String(), nullable=True))
    if "marketplace_public" not in task_columns:
        op.add_column(
            "tasks",
            sa.Column("marketplace_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "marketplace_listing_agent_id" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_listing_agent_id", sa.Uuid(), nullable=True))
    if "marketplace_attachments" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_attachments", sa.JSON(), nullable=True))
    if "marketplace_match_candidates" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_match_candidates", sa.JSON(), nullable=True))
    if "marketplace_delivery_artifacts" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_delivery_artifacts", sa.JSON(), nullable=True))
    if "marketplace_screenshots" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_screenshots", sa.JSON(), nullable=True))
    if "marketplace_delivery_note" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_delivery_note", sa.Text(), nullable=True))
    if "marketplace_failure_reason" not in task_columns:
        op.add_column("tasks", sa.Column("marketplace_failure_reason", sa.Text(), nullable=True))
    inspector = sa.inspect(bind)
    if "ix_tasks_marketplace_state" not in _index_names(inspector, "tasks"):
        op.create_index("ix_tasks_marketplace_state", "tasks", ["marketplace_state"], unique=False)
    if "ix_tasks_marketplace_task_type" not in _index_names(inspector, "tasks"):
        op.create_index(
            "ix_tasks_marketplace_task_type",
            "tasks",
            ["marketplace_task_type"],
            unique=False,
        )
    if "ix_tasks_marketplace_public" not in _index_names(inspector, "tasks"):
        op.create_index("ix_tasks_marketplace_public", "tasks", ["marketplace_public"], unique=False)
    if "ix_tasks_marketplace_listing_agent_id" not in _index_names(inspector, "tasks"):
        op.create_index(
            "ix_tasks_marketplace_listing_agent_id",
            "tasks",
            ["marketplace_listing_agent_id"],
            unique=False,
        )
    if "fk_tasks_marketplace_listing_agent_id_agents" not in _foreign_key_names(inspector, "tasks"):
        op.create_foreign_key(
            "fk_tasks_marketplace_listing_agent_id_agents",
            "tasks",
            "agents",
            ["marketplace_listing_agent_id"],
            ["id"],
        )

    if not inspector.has_table("payments"):
        op.create_table(
            "payments",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("task_id", sa.Uuid(), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(), nullable=False, server_default="cny"),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("payer_id", sa.Uuid(), nullable=False),
            sa.Column("payee_id", sa.Uuid(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False, server_default="mock"),
            sa.Column("provider_payment_id", sa.String(), nullable=True),
            sa.Column("provider_client_secret", sa.String(), nullable=True),
            sa.Column("platform_fee_amount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("payee_amount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("released_at", sa.DateTime(), nullable=True),
            sa.Column("refunded_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["payer_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["payee_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id", name="uq_payments_task_id"),
        )
    inspector = sa.inspect(bind)
    if "ix_payments_task_id" not in _index_names(inspector, "payments"):
        op.create_index("ix_payments_task_id", "payments", ["task_id"], unique=False)
    if "ix_payments_status" not in _index_names(inspector, "payments"):
        op.create_index("ix_payments_status", "payments", ["status"], unique=False)
    if "ix_payments_payer_id" not in _index_names(inspector, "payments"):
        op.create_index("ix_payments_payer_id", "payments", ["payer_id"], unique=False)
    if "ix_payments_payee_id" not in _index_names(inspector, "payments"):
        op.create_index("ix_payments_payee_id", "payments", ["payee_id"], unique=False)
    if "ix_payments_provider" not in _index_names(inspector, "payments"):
        op.create_index("ix_payments_provider", "payments", ["provider"], unique=False)
    if "ix_payments_provider_payment_id" not in _index_names(inspector, "payments"):
        op.create_index(
            "ix_payments_provider_payment_id",
            "payments",
            ["provider_payment_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("payments"):
        payment_indexes = _index_names(inspector, "payments")
        for index_name in (
            "ix_payments_provider_payment_id",
            "ix_payments_provider",
            "ix_payments_payee_id",
            "ix_payments_payer_id",
            "ix_payments_status",
            "ix_payments_task_id",
        ):
            if index_name in payment_indexes:
                op.drop_index(index_name, table_name="payments")
        op.drop_table("payments")

    inspector = sa.inspect(bind)
    task_indexes = _index_names(inspector, "tasks")
    task_columns = _column_names(inspector, "tasks")
    task_foreign_keys = _foreign_key_names(inspector, "tasks")
    for index_name in (
        "ix_tasks_marketplace_listing_agent_id",
        "ix_tasks_marketplace_public",
        "ix_tasks_marketplace_task_type",
        "ix_tasks_marketplace_state",
    ):
        if index_name in task_indexes:
            op.drop_index(index_name, table_name="tasks")
    if "fk_tasks_marketplace_listing_agent_id_agents" in task_foreign_keys:
        op.drop_constraint("fk_tasks_marketplace_listing_agent_id_agents", "tasks", type_="foreignkey")
    for column_name in (
        "marketplace_failure_reason",
        "marketplace_delivery_note",
        "marketplace_screenshots",
        "marketplace_delivery_artifacts",
        "marketplace_match_candidates",
        "marketplace_attachments",
        "marketplace_listing_agent_id",
        "marketplace_public",
        "marketplace_budget_currency",
        "marketplace_budget_amount",
        "marketplace_task_type",
        "marketplace_state",
    ):
        if column_name in task_columns:
            op.drop_column("tasks", column_name)

    inspector = sa.inspect(bind)
    agent_indexes = _index_names(inspector, "agents")
    agent_columns = _column_names(inspector, "agents")
    agent_foreign_keys = _foreign_key_names(inspector, "agents")
    for index_name in ("ix_agents_marketplace_enabled", "ix_agents_owner_id"):
        if index_name in agent_indexes:
            op.drop_index(index_name, table_name="agents")
    if "fk_agents_owner_id_users" in agent_foreign_keys:
        op.drop_constraint("fk_agents_owner_id_users", "agents", type_="foreignkey")
    for column_name in (
        "marketplace_enabled",
        "score",
        "max_concurrency",
        "skill_tags",
        "availability",
        "pricing",
        "skills",
        "gateway_url",
        "owner_id",
    ):
        if column_name in agent_columns:
            op.drop_column("agents", column_name)

    inspector = sa.inspect(bind)
    user_indexes = _index_names(inspector, "users")
    user_columns = _column_names(inspector, "users")
    if "ix_users_account_role" in user_indexes:
        op.drop_index("ix_users_account_role", table_name="users")
    for column_name in ("wechat_handle", "company_name", "account_role"):
        if column_name in user_columns:
            op.drop_column("users", column_name)
