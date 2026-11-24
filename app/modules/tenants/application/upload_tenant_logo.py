from pathlib import Path

from app.modules.tenants.application.errors import (
    InvalidTenantInputError,
    TenantNotFoundError,
)
from app.modules.tenants.domain.repository import TenantRepository

ALLOWED_MIME_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}

MAX_LOGO_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB


class UploadTenantLogo:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        assets_storage_dir: str,
        assets_public_url_prefix: str,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._assets_storage_dir = Path(assets_storage_dir)
        self._assets_public_url_prefix = assets_public_url_prefix.rstrip("/")

    async def execute(
        self,
        *,
        subdomain: str,
        file_bytes: bytes,
        content_type: str | None,
        filename: str | None = None,
    ) -> str:
        clean_subdomain = subdomain.strip().lower()
        tenant = await self._tenant_repo.get_by_subdomain(clean_subdomain)
        if tenant is None:
            raise TenantNotFoundError(
                f"Tenant with subdomain '{subdomain}' was not found."
            )

        if not file_bytes:
            raise InvalidTenantInputError("Uploaded logo file is empty.")

        if len(file_bytes) > MAX_LOGO_FILE_SIZE_BYTES:
            raise InvalidTenantInputError(
                "Logo file exceeds the maximum allowed size of 2MB."
            )

        # Determine extension by mime type or file extension
        normalized_content_type = (content_type or "").lower().split(";")[0].strip()
        ext = ALLOWED_MIME_TYPES.get(normalized_content_type)
        if not ext and filename:
            suffix = Path(filename).suffix.lower()
            if suffix in (".png", ".jpg", ".jpeg", ".svg", ".webp"):
                ext = suffix

        if not ext:
            raise InvalidTenantInputError(
                "Invalid image format. Allowed formats are PNG, JPEG, SVG, and WebP."
            )

        # Ensure directory exists: /var/www/skyknow/assets/tenants/<subdomain>/
        tenant_asset_dir = self._assets_storage_dir / "tenants" / clean_subdomain
        tenant_asset_dir.mkdir(parents=True, exist_ok=True)

        target_file_path = tenant_asset_dir / f"logo{ext}"
        target_file_path.write_bytes(file_bytes)

        # Construct public URL served by Nginx: /assets/tenants/<subdomain>/logo.<ext>
        public_logo_url = (
            f"{self._assets_public_url_prefix}/tenants/{clean_subdomain}/logo{ext}"
        )

        await self._tenant_repo.update_tenant_logo_url(
            subdomain=clean_subdomain,
            logo_url=public_logo_url,
        )

        return public_logo_url
