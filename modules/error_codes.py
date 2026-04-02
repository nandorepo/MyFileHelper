from __future__ import annotations

# Error code ranges (convention, not enforcement):
# - 40001-40099: message validation / pagination errors
# - 40015-40099: upload validation errors
# - 403xx: access control failures
# - 404xx: missing resources
# - 413xx: payload size violations
# - 500xx: server-side merge/storage failures

# Message route error codes
MSG_INVALID_PAGINATION = 40001
MSG_LIMIT_NOT_POSITIVE = 40002
MSG_INVALID_SINCE = 40003
MSG_ATTACHMENT_IDS_NOT_ARRAY = 40004
MSG_TEXT_OR_ATTACHMENTS_REQUIRED = 40005
MSG_ATTACHMENT_NOT_FOUND = 40402

# Upload route error codes
UPLOAD_FILE_REQUIRED = 40015
UPLOAD_AUTO_CHUNK_DISABLED = 40016
UPLOAD_EMPTY_FILE = 40017
UPLOAD_FILE_TOO_LARGE = 41301
UPLOAD_QUEUE_TIMEOUT = 50301
UPLOAD_MERGE_VERIFICATION_FAILED = 50001
# Core route/media error codes
ROUTE_ACCESS_FORBIDDEN = 40301
ROUTE_MEDIA_FILE_NOT_FOUND = 40401


ERROR_CODE_CATALOG = {
    MSG_INVALID_PAGINATION: {
        "name": "MSG_INVALID_PAGINATION",
        "http_status": 400,
        "scope": "messages",
        "description": "Pagination query parameters cannot be parsed as integers.",
    },
    MSG_LIMIT_NOT_POSITIVE: {
        "name": "MSG_LIMIT_NOT_POSITIVE",
        "http_status": 400,
        "scope": "messages",
        "description": "The `limit` query parameter must be greater than zero.",
    },
    MSG_INVALID_SINCE: {
        "name": "MSG_INVALID_SINCE",
        "http_status": 400,
        "scope": "messages",
        "description": "The `since` timestamp is not a valid ISO8601 UTC value.",
    },
    MSG_ATTACHMENT_IDS_NOT_ARRAY: {
        "name": "MSG_ATTACHMENT_IDS_NOT_ARRAY",
        "http_status": 400,
        "scope": "messages",
        "description": "`attachment_ids` must be submitted as an array.",
    },
    MSG_TEXT_OR_ATTACHMENTS_REQUIRED: {
        "name": "MSG_TEXT_OR_ATTACHMENTS_REQUIRED",
        "http_status": 400,
        "scope": "messages",
        "description": "Creating a message requires text, attachments, or both.",
    },
    MSG_ATTACHMENT_NOT_FOUND: {
        "name": "MSG_ATTACHMENT_NOT_FOUND",
        "http_status": 404,
        "scope": "messages",
        "description": "One of the requested attachment IDs does not exist in memory.",
    },
    UPLOAD_FILE_REQUIRED: {
        "name": "UPLOAD_FILE_REQUIRED",
        "http_status": 400,
        "scope": "upload",
        "description": "The multipart request must include a `file` field.",
    },
    UPLOAD_AUTO_CHUNK_DISABLED: {
        "name": "UPLOAD_AUTO_CHUNK_DISABLED",
        "http_status": 400,
        "scope": "upload",
        "description": "Client requested auto chunking while the feature is disabled.",
    },
    UPLOAD_EMPTY_FILE: {
        "name": "UPLOAD_EMPTY_FILE",
        "http_status": 400,
        "scope": "upload",
        "description": "The uploaded stream produced no bytes.",
    },
    UPLOAD_FILE_TOO_LARGE: {
        "name": "UPLOAD_FILE_TOO_LARGE",
        "http_status": 413,
        "scope": "upload",
        "description": "The uploaded payload exceeded the configured file size limit.",
    },
    UPLOAD_MERGE_VERIFICATION_FAILED: {
        "name": "UPLOAD_MERGE_VERIFICATION_FAILED",
        "http_status": 500,
        "scope": "upload",
        "description": "Chunk merge verification failed after writing the upload.",
    },
    UPLOAD_QUEUE_TIMEOUT: {
        "name": "UPLOAD_QUEUE_TIMEOUT",
        "http_status": 503,
        "scope": "upload",
        "description": "Upload could not start within the configured queue timeout.",
    },
    ROUTE_ACCESS_FORBIDDEN: {
        "name": "ROUTE_ACCESS_FORBIDDEN",
        "http_status": 403,
        "scope": "routes",
        "description": "The request IP address is not in the configured allowlist.",
    },
    ROUTE_MEDIA_FILE_NOT_FOUND: {
        "name": "ROUTE_MEDIA_FILE_NOT_FOUND",
        "http_status": 404,
        "scope": "routes",
        "description": "The upload entry exists, but the stored file is missing on disk.",
    },
}


__all__ = [
    "MSG_INVALID_PAGINATION",
    "MSG_LIMIT_NOT_POSITIVE",
    "MSG_INVALID_SINCE",
    "MSG_ATTACHMENT_IDS_NOT_ARRAY",
    "MSG_TEXT_OR_ATTACHMENTS_REQUIRED",
    "MSG_ATTACHMENT_NOT_FOUND",
    "UPLOAD_FILE_REQUIRED",
    "UPLOAD_AUTO_CHUNK_DISABLED",
    "UPLOAD_EMPTY_FILE",
    "UPLOAD_FILE_TOO_LARGE",
    "UPLOAD_QUEUE_TIMEOUT",
    "UPLOAD_MERGE_VERIFICATION_FAILED",
    "ROUTE_ACCESS_FORBIDDEN",
    "ROUTE_MEDIA_FILE_NOT_FOUND",
    "ERROR_CODE_CATALOG",
]
