from __future__ import annotations

import ipaddress

from flask import request


def request_ip(security_config) -> str:
    if security_config.docs_trust_x_forwarded_for:
        forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if forwarded_for:
            return forwarded_for
    return request.remote_addr or ""


def docs_access_allowed(security_config) -> tuple[bool, tuple | None]:
    if not security_config.docs_enabled:
        return False, ("Not Found", 404)

    if security_config.docs_acl_enabled:
        ip_raw = request_ip(security_config)
        try:
            ip_obj = ipaddress.ip_address(ip_raw)
        except ValueError:
            return False, ("Forbidden", 403)

        allowed = ip_raw in security_config.docs_allow_ips
        if not allowed:
            for cidr in security_config.docs_allow_cidrs:
                try:
                    if ip_obj in ipaddress.ip_network(cidr, strict=False):
                        allowed = True
                        break
                except ValueError:
                    continue

        if not allowed:
            return False, ("Forbidden", 403)

    if security_config.docs_auth_enabled:
        if security_config.docs_auth_type == "basic":
            auth = request.authorization
            if (
                not auth
                or auth.username != security_config.docs_auth_username
                or auth.password != security_config.docs_auth_password
            ):
                return False, ("Unauthorized", 401, {"WWW-Authenticate": "Basic realm=docs"})
        elif security_config.docs_auth_type == "api_key":
            provided = request.headers.get(security_config.docs_auth_header_name, "")
            if provided != security_config.docs_auth_api_key:
                return False, ("Unauthorized", 401)

    return True, None


def openapi_spec(api_config) -> dict:
    base = api_config.base_path.rstrip("/")
    version = api_config.default_version
    api_root = f"{base}/{version}"

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "MyFileHelper API",
            "version": version,
            "description": "Versionless aliases are enabled. Example: /api/messages == /api/v1/messages",
        },
        "paths": {
            f"{api_root}/messages": {
                "get": {
                    "summary": "List messages",
                    "parameters": [
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                        {"name": "cursor", "in": "query", "schema": {"type": "integer", "default": 0}},
                        {"name": "since", "in": "query", "schema": {"type": "string", "format": "date-time"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                },
                "post": {
                    "summary": "Send message",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "user": {"type": "string"},
                                        "text": {"type": "string"},
                                        "attachment_ids": {"type": "array", "items": {"type": "string"}},
                                        "client_msg_id": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                },
            },
            f"{api_root}/upload": {
                "post": {
                    "summary": "Auto upload file",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "file": {"type": "string", "format": "binary"},
                                        "chunked": {"type": "boolean", "default": False},
                                        "create_message": {"type": "boolean", "default": False},
                                        "client_msg_id": {"type": "string"},
                                    },
                                    "required": ["file"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                }
            },
            f"{api_root}/upload/init": {
                "post": {
                    "summary": "Init chunk upload",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                }
            },
            f"{api_root}/upload/chunk": {
                "post": {
                    "summary": "Upload chunk",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                }
            },
            f"{api_root}/upload/complete": {
                "post": {
                    "summary": "Complete chunk upload",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiResponse"}}},
                        }
                    },
                }
            },
            f"{api_root}/download/{{file_id}}": {
                "get": {
                    "summary": "Download file",
                    "parameters": [
                        {"name": "file_id", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "inline", "in": "query", "schema": {"type": "boolean", "default": False}},
                    ],
                    "responses": {"200": {"description": "File stream"}},
                }
            },
        },
        "components": {
            "schemas": {
                "ApiResponse": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "integer"},
                        "message": {"type": "string"},
                        "data": {"type": "object", "nullable": True},
                    },
                }
            }
        },
    }
