from typing import Annotated, Literal
from uuid import UUID

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field


class ProvisionTenantForm:
    """Form parameters for tenant provisioning with direct logo file upload via Swagger/multipart."""

    def __init__(
        self,
        subdomain: Annotated[
            str,
            Form(
                min_length=2,
                max_length=63,
                description="Tenant subdomain (lowercase alphanumeric, hyphens allowed).",
                examples=["cbe"],
            ),
        ],
        admin_email: Annotated[
            str,
            Form(
                pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
                max_length=255,
                description="Email address for the initial tenant administrator.",
                examples=["admin@cbe.et"],
            ),
        ],
        admin_name: Annotated[
            str,
            Form(
                min_length=1,
                max_length=150,
                description="Full name of the initial tenant administrator.",
                examples=["CBE Admin"],
            ),
        ],
        name: Annotated[
            str | None,
            Form(
                max_length=150,
                description="Display name of the organization (defaults to formatted subdomain).",
                examples=["Commercial Bank of Ethiopia"],
            ),
        ] = None,
        temporary_password: Annotated[
            str | None,
            Form(
                min_length=8,
                description="Temporary password for the administrator (optional).",
                examples=["TempPass123!"],
            ),
        ] = None,
        hosting_mode: Annotated[
            Literal["shared", "dedicated"],
            Form(
                description="Hosting isolation tier.",
                examples=["shared"],
            ),
        ] = "shared",
        custom_domain: Annotated[
            str | None,
            Form(
                max_length=255,
                description="Custom domain mapping for tenant (optional).",
                examples=["portal.cbe.et"],
            ),
        ] = None,
        primary_color: Annotated[
            str | None,
            Form(
                pattern=r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$",
                description="Primary brand color in hex format (e.g. #9333EA).",
                examples=["#9333EA"],
            ),
        ] = None,
        logo: Annotated[
            UploadFile | None,
            File(
                description="Upload tenant brand logo file (PNG, JPEG, SVG, WebP, max 2MB).",
            ),
        ] = None,
    ) -> None:
        self.subdomain = subdomain
        self.admin_email = admin_email
        self.admin_name = admin_name
        self.name = name
        self.temporary_password = temporary_password
        self.hosting_mode = hosting_mode
        self.custom_domain = custom_domain
        self.primary_color = primary_color
        self.logo = logo


class ProvisionTenantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subdomain: str = Field(
        ...,
        min_length=2,
        max_length=63,
        description="Tenant subdomain (lowercase alphanumeric, hyphens allowed).",
        examples=["acme"],
    )
    admin_email: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        max_length=255,
        description="Email address for the initial tenant administrator.",
        examples=["admin@acme.com"],
    )
    admin_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Full name of the initial tenant administrator.",
        examples=["Acme Administrator"],
    )
    name: str | None = Field(
        default=None,
        max_length=150,
        description="Display name of the organization (defaults to formatted subdomain).",
        examples=["Acme Corporation"],
    )
    temporary_password: str | None = Field(
        default=None,
        min_length=8,
        description="Temporary password for the administrator (optional).",
        examples=["TempPass123!"],
    )
    hosting_mode: Literal["shared", "dedicated"] = Field(
        default="shared",
        description="Hosting isolation tier.",
    )
    custom_domain: str | None = Field(
        default=None,
        max_length=255,
        description="Custom domain mapping for tenant.",
        examples=["portal.acme.com"],
    )
    primary_color: str | None = Field(
        default=None,
        pattern=r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$",
        description="Primary brand color in hex format (e.g. #1E40AF).",
        examples=["#1E40AF"],
    )
    logo_url: str | None = Field(
        default=None,
        max_length=500,
        description="Public URL or path to the tenant's brand logo.",
        examples=["https://assets.acme.com/logo.png"],
    )


class ProvisionTenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    name: str
    subdomain: str
    schema_name: str
    custom_domain: str | None
    hosting_mode: str
    admin_user_id: UUID
    admin_email: str
    admin_name: str
    primary_color: str | None = None
    logo_url: str | None = None
    message: str = "Tenant provisioned successfully."


class TenantBrandingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    subdomain: str
    custom_domain: str | None
    primary_color: str | None
    logo_url: str | None


class UploadTenantLogoResponse(BaseModel):
    subdomain: str
    logo_url: str
    message: str = "Tenant logo uploaded successfully."
