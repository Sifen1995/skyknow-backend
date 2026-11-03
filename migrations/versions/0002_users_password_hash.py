from alembic import op

revision = "0002_users_password_hash"
down_revision = "0001_skyknow_mvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN password_hash text")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN password_hash")
