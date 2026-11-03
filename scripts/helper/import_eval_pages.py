import asyncio
from datetime import UTC, datetime
from pathlib import Path

import frontmatter  # parses markdown frontmatter (metadata + content)
from sqlalchemy import select, text

from app.core.db import AsyncSessionLocal
from app.modules.identity.domain.enums import RoleName, UserStatus
from app.modules.identity.domain.models import OrgUnit, RoleAssignment, User
from app.modules.knowledge.domain.enums import (
    PageVisibility,
    TemplateType,
    VersionState,
)
from app.modules.knowledge.domain.models import (
    Page,
    PageAudience,
    PageLanguage,
    PageVersion,
)

EVAL_PAGES_DIR = Path("eval/pages")


async def import_eval_pages():
    if not EVAL_PAGES_DIR.exists():
        print(f"Directory {EVAL_PAGES_DIR} does not exist. Skipping import.")
        return

    async with AsyncSessionLocal() as session:
        author_result = await session.execute(
            select(User, OrgUnit)
            .join(RoleAssignment, RoleAssignment.user_id == User.id)
            .join(OrgUnit, OrgUnit.id == RoleAssignment.org_unit_id)
            .where(
                RoleAssignment.role == RoleName.AUTHOR,
                User.status == UserStatus.ACTIVE,
                OrgUnit.is_active.is_(True),
            )
            .order_by(User.email, OrgUnit.path)
            .limit(1)
        )
        author_record = author_result.first()

        if not author_record:
            raise RuntimeError(
                "Seed an active user with an author role before importing pages."
            )

        page_owner, owner_org_unit = author_record

        async def find_scoped_user(role: RoleName) -> User:
            result = await session.execute(
                select(User)
                .join(RoleAssignment, RoleAssignment.user_id == User.id)
                .join(OrgUnit, OrgUnit.id == RoleAssignment.org_unit_id)
                .where(
                    RoleAssignment.role == role,
                    User.status == UserStatus.ACTIVE,
                    OrgUnit.is_active.is_(True),
                    text("CAST(:owner_path AS ltree) <@ org_units.path"),
                )
                .order_by(User.email)
                .limit(1),
                {"owner_path": owner_org_unit.path},
            )
            scoped_user = result.scalars().first()
            if scoped_user is None:
                raise RuntimeError(
                    f"No active {role.value} role covers owner unit {owner_org_unit.path}."
                )
            return scoped_user

        if not page_owner or not owner_org_unit:
            return

        # 2. Iterate through all markdown files in eval/pages
        md_files = sorted(EVAL_PAGES_DIR.glob("*.md"))
        print(f"Found {len(md_files)} evaluation markdown files to import.")

        for file_path in md_files:
            print(f"Processing: {file_path.name}")

            # Read markdown file with frontmatter
            post = frontmatter.load(file_path)
            metadata = post.metadata
            body_content = post.content

            title = metadata.get("title", file_path.stem.replace("_", " ").title())
            template_str = metadata.get("template", "howto")
            lang_code = metadata.get("language", "en")
            visibility_str = metadata.get("visibility", "restricted")

            # Map strings to enums safely
            template = (
                TemplateType(template_str)
                if template_str in [t.value for t in TemplateType]
                else TemplateType.HOWTO
            )
            visibility = (
                PageVisibility(visibility_str)
                if visibility_str in [v.value for v in PageVisibility]
                else PageVisibility.RESTRICTED
            )

            # 3. Create the parent Page container
            page = Page(
                template=template,
                owner_org_unit_id=owner_org_unit.id,
                owner_id=page_owner.id,
                created_by=page_owner.id,
                visibility=visibility,
                is_customer_visible=metadata.get("customer_visible", False),
            )
            session.add(page)
            await session.flush()  # Generates page.id

            # 4. Create the PageAudience link (linking page to default org unit)
            audience = PageAudience(
                page_id=page.id, org_unit_id=owner_org_unit.id, include_descendants=True
            )
            session.add(audience)

            # 5. Create the PageLanguage tracking row
            page_lang = PageLanguage(page_id=page.id, language_code=lang_code)
            session.add(page_lang)
            await session.flush()  # Generates page_lang.id

            # 6. Create the initial Published or Draft PageVersion (Eval files are usually imported as published to test RAG)
            version_state = (
                VersionState.PUBLISHED
                if metadata.get("published", True)
                else VersionState.DRAFT
            )

            workflow_time = datetime.now(UTC)
            reviewer = (
                await find_scoped_user(RoleName.REVIEWER)
                if version_state == VersionState.PUBLISHED
                else None
            )
            publisher = (
                await find_scoped_user(RoleName.PUBLISHER)
                if version_state == VersionState.PUBLISHED
                else None
            )

            page_version = PageVersion(
                page_language_id=page_lang.id,
                version_number=1,
                title=title,
                summary=metadata.get("summary", ""),
                content={
                    "blocks": [{"type": "paragraph", "text": body_content}]
                },  # Structured block storage as per SDS
                content_text=body_content,  # Plain text copy for chunking
                state=version_state,
                created_by=page_owner.id,
                submitted_at=workflow_time
                if version_state == VersionState.PUBLISHED
                else None,
                approved_by=reviewer.id if reviewer else None,
                approved_at=workflow_time if reviewer else None,
                published_by=publisher.id if publisher else None,
                published_at=workflow_time if publisher else None,
            )
            session.add(page_version)

        # Commit all imported pages to the database in a single transaction
        await session.commit()
        print("Successfully imported all evaluation pages into the database!")


if __name__ == "__main__":
    asyncio.run(import_eval_pages())
