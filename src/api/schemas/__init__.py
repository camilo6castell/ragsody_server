"""
Pydantic schemas for the REST API, organized by domain -- one file per
router (chat.py, files.py, config.py), mirroring src/api/routers/.

This package re-exports the public schemas so callers can continue to
use `from src.api.schemas import QueryRequest` without depending on the
submodule layout.
"""

from src.api.schemas.attachments import (
    AttachmentInfo,
    AttachmentsResponse,
)
from src.api.schemas.chat import (
    CollectionsResponse,
    GenerationOptions,
    QueryRequest,
    QueryResponse,
)
from src.api.schemas.config import ProviderInfo, ProvidersResponse
from src.api.schemas.files import (
    DeleteResponse,
    EphemeralFileInfo,
    EphemeralFilesResponse,
    FileUploadResponse,
)

__all__ = [
    "CollectionsResponse",
    "GenerationOptions",
    "QueryRequest",
    "QueryResponse",
    "ProviderInfo",
    "ProvidersResponse",
    "DeleteResponse",
    "EphemeralFileInfo",
    "EphemeralFilesResponse",
    "FileUploadResponse",
    "AttachmentInfo",
    "AttachmentsResponse",
]
