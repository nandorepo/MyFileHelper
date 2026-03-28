# Error Codes

Canonical source: `modules/error_codes.py` (`ERROR_CODE_CATALOG`).

This document is the human-readable index for API error codes.
If code and docs differ, `modules/error_codes.py` is authoritative.

## JSON Envelope Reminder

Error responses for `/ui/*` JSON APIs use this shape:

```json
{
  "code": 40015,
  "message": "file is required",
  "data": null
}
```

## Code Index

| Code | Constant | HTTP | Scope | Description |
|---|---|---:|---|---|
| 40001 | `MSG_INVALID_PAGINATION` | 400 | `messages` | Pagination query parameters cannot be parsed as integers. |
| 40002 | `MSG_LIMIT_NOT_POSITIVE` | 400 | `messages` | The `limit` query parameter must be greater than zero. |
| 40003 | `MSG_INVALID_SINCE` | 400 | `messages` | The `since` timestamp is not a valid ISO8601 UTC value. |
| 40004 | `MSG_ATTACHMENT_IDS_NOT_ARRAY` | 400 | `messages` | `attachment_ids` must be submitted as an array. |
| 40005 | `MSG_TEXT_OR_ATTACHMENTS_REQUIRED` | 400 | `messages` | Creating a message requires text, attachments, or both. |
| 40402 | `MSG_ATTACHMENT_NOT_FOUND` | 404 | `messages` | One of the requested attachment IDs does not exist in memory. |
| 40015 | `UPLOAD_FILE_REQUIRED` | 400 | `upload` | The multipart request must include a `file` field. |
| 40016 | `UPLOAD_AUTO_CHUNK_DISABLED` | 400 | `upload` | Client requested auto chunking while the feature is disabled. |
| 40017 | `UPLOAD_EMPTY_FILE` | 400 | `upload` | The uploaded stream produced no bytes. |
| 41301 | `UPLOAD_FILE_TOO_LARGE` | 413 | `upload` | The uploaded payload exceeded the configured file size limit. |
| 50001 | `UPLOAD_MERGE_VERIFICATION_FAILED` | 500 | `upload` | Chunk merge verification failed after writing the upload. |
| 40301 | `ROUTE_ACCESS_FORBIDDEN` | 403 | `routes` | The request IP address is not in the configured allowlist. |
| 40401 | `ROUTE_MEDIA_FILE_NOT_FOUND` | 404 | `routes` | The upload entry exists, but the stored file is missing on disk. |

## Endpoint Reverse Lookup

Use this section when you know the endpoint first and need relevant error codes quickly.

### `GET /ui/messages`

- `40001` `MSG_INVALID_PAGINATION`
- `40002` `MSG_LIMIT_NOT_POSITIVE`
- `40003` `MSG_INVALID_SINCE`

### `POST /ui/messages`

- `40004` `MSG_ATTACHMENT_IDS_NOT_ARRAY`
- `40005` `MSG_TEXT_OR_ATTACHMENTS_REQUIRED`
- `40402` `MSG_ATTACHMENT_NOT_FOUND`

### `POST /ui/upload`

- `40015` `UPLOAD_FILE_REQUIRED`
- `40016` `UPLOAD_AUTO_CHUNK_DISABLED`
- `40017` `UPLOAD_EMPTY_FILE`
- `41301` `UPLOAD_FILE_TOO_LARGE`
- `50001` `UPLOAD_MERGE_VERIFICATION_FAILED`

### Route-Level Guard and Media

- Access control guard (`before_request`): `40301` `ROUTE_ACCESS_FORBIDDEN`
- `GET /media/<file_id>` disk-missing case: `40401` `ROUTE_MEDIA_FILE_NOT_FOUND`

## Non-JSON Route Notes

- `/files` returns HTML.
- `/media/<file_id>` returns file bytes on success.
- `/ui/client-log` returns `204 No Content`.



