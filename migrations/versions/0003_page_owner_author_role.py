from alembic import op

revision = "0003_page_owner_author"
down_revision = "0002_users_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
		DO $$
		BEGIN
			IF EXISTS (
				SELECT 1
				FROM pages p
				JOIN org_units page_scope ON page_scope.id = p.owner_org_unit_id
				WHERE NOT EXISTS (
					SELECT 1
					FROM role_assignments ra
					JOIN users u ON u.id = ra.user_id AND u.status = 'active'
					JOIN org_units role_scope ON role_scope.id = ra.org_unit_id
					WHERE ra.user_id = p.owner_id
					  AND ra.role = 'author'
					  AND page_scope.path <@ role_scope.path
				)
			) THEN
				RAISE EXCEPTION
					'Cannot enforce author ownership: existing pages have owners without an active author role in scope';
			END IF;
		END $$
		"""
    )
    op.execute(
        """
		CREATE FUNCTION pages_require_author_owner() RETURNS trigger
		LANGUAGE plpgsql AS $$
		BEGIN
			IF NOT EXISTS (
				SELECT 1
				FROM role_assignments ra
				JOIN users u ON u.id = ra.user_id AND u.status = 'active'
				JOIN org_units role_scope ON role_scope.id = ra.org_unit_id
				JOIN org_units page_scope ON page_scope.id = NEW.owner_org_unit_id
				WHERE ra.user_id = NEW.owner_id
				  AND ra.role = 'author'
				  AND page_scope.path <@ role_scope.path
			) THEN
				RAISE EXCEPTION 'page owner must have an active author role covering the owner unit'
					USING ERRCODE = 'insufficient_privilege';
			END IF;
			RETURN NEW;
		END $$
		"""
    )
    op.execute(
        """
		CREATE TRIGGER pages_author_owner_trg
		BEFORE INSERT OR UPDATE OF owner_id, owner_org_unit_id ON pages
		FOR EACH ROW EXECUTE FUNCTION pages_require_author_owner()
		"""
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS pages_author_owner_trg ON pages")
    op.execute("DROP FUNCTION IF EXISTS pages_require_author_owner()")
