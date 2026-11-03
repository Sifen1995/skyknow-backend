import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_identity_refresh_tokens"
down_revision = "0003_page_owner_author"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "identity_refresh_tokens_user_id_idx",
        "identity_refresh_tokens",
        ["user_id"],
    )
    op.create_index(
        "identity_refresh_tokens_family_id_idx",
        "identity_refresh_tokens",
        ["family_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "identity_refresh_tokens_family_id_idx",
        table_name="identity_refresh_tokens",
    )
    op.drop_index(
        "identity_refresh_tokens_user_id_idx",
        table_name="identity_refresh_tokens",
    )
    op.drop_table("identity_refresh_tokens")