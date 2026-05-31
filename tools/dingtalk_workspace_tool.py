"""Read-only dws bridge tools for DingTalk Workspace docs, drive, and wiki.

These tools intentionally expose only read/search/list/info operations. They
leave authentication, tenant authorization, token refresh, and auditing to the
official ``dws`` CLI from DingTalk Workspace CLI.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from tools.registry import registry, tool_error, tool_result


_DWS_BIN = "dws"
_DEFAULT_TIMEOUT_SECONDS = 60
_MAX_STDOUT_CHARS = 200_000


def _check_dws() -> bool:
    return shutil.which(_DWS_BIN) is not None


def _parse_json_maybe(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _run_dws(argv: list[str], timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> str:
    if not _check_dws():
        return tool_error(
            "dws is not installed. Install DingTalk Workspace CLI first.",
            setup={
                "macos_linux": "curl -fsSL https://raw.githubusercontent.com/DingTalk-Real-AI/dingtalk-workspace-cli/main/scripts/install.sh | sh",
                "npm": "npm install -g dingtalk-workspace-cli",
                "login": "dws auth login",
                "device_login": "dws auth login --device",
            },
        )

    final_argv = [_DWS_BIN, *argv]
    if "-f" not in argv and "--format" not in argv:
        final_argv.extend(["-f", "json"])

    try:
        completed = subprocess.run(
            final_argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return tool_error("dws command timed out", argv=final_argv)

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    parsed_stdout = _parse_json_maybe(stdout[:_MAX_STDOUT_CHARS])
    parsed_stderr = _parse_json_maybe(stderr)

    if completed.returncode != 0:
        return tool_error(
            "dws command failed",
            code=completed.returncode,
            argv=final_argv,
            stdout=parsed_stdout,
            stderr=parsed_stderr,
            hint={
                "auth_status": "dws auth status -f json",
                "login": "dws auth login",
                "device_login": "dws auth login --device",
                "admin_note": "If the organization has not enabled CLI access, ask the DingTalk admin to approve CLI access first.",
            },
        )

    return tool_result(
        success=True,
        argv=final_argv,
        stdout=parsed_stdout,
        stderr=parsed_stderr,
    )


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _append_optional_flags(argv: list[str], args: dict, flags: dict[str, str]) -> None:
    for key, flag in flags.items():
        value = args.get(key)
        if value is not None and value != "":
            argv.extend([flag, str(value)])


DINGTALK_AUTH_STATUS_SCHEMA = {
    "name": "dingtalk_auth_status",
    "description": "Check whether DingTalk Workspace CLI (dws) is installed and logged in.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _handle_auth_status(args: dict, **kwargs) -> str:
    return _run_dws(["auth", "status"], timeout=30)


DINGTALK_DOC_SEARCH_SCHEMA = {
    "name": "dingtalk_doc_search",
    "description": (
        "Search DingTalk documents through the official dws CLI. Read-only; "
        "runs as the logged-in user."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword."},
            "page_size": {"type": "integer", "description": "Page size.", "default": 10},
            "page_token": {"type": "string", "description": "Pagination token."},
            "workspace_ids": {"type": "string", "description": "Comma-separated workspace IDs."},
            "extensions": {"type": "string", "description": "Comma-separated extensions, e.g. docx,axls."},
            "created_from": {"type": "string", "description": "Created time lower bound."},
            "created_to": {"type": "string", "description": "Created time upper bound."},
            "visited_from": {"type": "string", "description": "Visited time lower bound."},
            "visited_to": {"type": "string", "description": "Visited time upper bound."},
            "creator_uids": {"type": "string", "description": "Comma-separated creator user IDs."},
            "editor_uids": {"type": "string", "description": "Comma-separated editor user IDs."},
            "mentioned_uids": {"type": "string", "description": "Comma-separated mentioned user IDs."},
        },
        "required": ["query"],
    },
}


def _handle_doc_search(args: dict, **kwargs) -> str:
    query = str(args.get("query") or "").strip()
    if not query:
        return tool_error("query is required")
    page_size = _bounded_int(args.get("page_size"), 10, 1, 50)
    argv = ["doc", "search", "--query", query, "--page-size", str(page_size)]
    _append_optional_flags(
        argv,
        args,
        {
            "page_token": "--page-token",
            "workspace_ids": "--workspace-ids",
            "extensions": "--extensions",
            "created_from": "--created-from",
            "created_to": "--created-to",
            "visited_from": "--visited-from",
            "visited_to": "--visited-to",
            "creator_uids": "--creator-uids",
            "editor_uids": "--editor-uids",
            "mentioned_uids": "--mentioned-uids",
        },
    )
    return _run_dws(argv)


DINGTALK_DOC_READ_SCHEMA = {
    "name": "dingtalk_doc_read",
    "description": "Read DingTalk document content by node ID. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {"node": {"type": "string", "description": "DingTalk document nodeId."}},
        "required": ["node"],
    },
}


def _handle_doc_read(args: dict, **kwargs) -> str:
    node = str(args.get("node") or "").strip()
    if not node:
        return tool_error("node is required")
    return _run_dws(["doc", "read", "--node", node], timeout=120)


DINGTALK_DOC_INFO_SCHEMA = {
    "name": "dingtalk_doc_info",
    "description": "Get DingTalk document metadata by node ID. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {"node": {"type": "string", "description": "DingTalk document nodeId."}},
        "required": ["node"],
    },
}


def _handle_doc_info(args: dict, **kwargs) -> str:
    node = str(args.get("node") or "").strip()
    if not node:
        return tool_error("node is required")
    return _run_dws(["doc", "info", "--node", node])


DINGTALK_WIKI_SPACE_SEARCH_SCHEMA = {
    "name": "dingtalk_wiki_space_search",
    "description": "Search DingTalk wiki spaces by keyword. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "Search keyword."},
            "limit": {"type": "integer", "description": "Result limit, max 20.", "default": 10},
        },
        "required": ["keyword"],
    },
}


def _handle_wiki_space_search(args: dict, **kwargs) -> str:
    keyword = str(args.get("keyword") or "").strip()
    if not keyword:
        return tool_error("keyword is required")
    limit = _bounded_int(args.get("limit"), 10, 1, 20)
    return _run_dws(["wiki", "space", "search", "--keyword", keyword, "--limit", str(limit)])


DINGTALK_WIKI_SPACE_LIST_SCHEMA = {
    "name": "dingtalk_wiki_space_list",
    "description": "List DingTalk wiki spaces accessible to the logged-in user. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "description": "Wiki space type: myWikiSpace or orgWikiSpace.",
                "default": "orgWikiSpace",
            },
            "limit": {"type": "integer", "description": "Page size, max 50.", "default": 20},
            "page_token": {"type": "string", "description": "Pagination token."},
        },
        "required": [],
    },
}


def _handle_wiki_space_list(args: dict, **kwargs) -> str:
    limit = _bounded_int(args.get("limit"), 20, 1, 50)
    space_type = str(args.get("type") or "orgWikiSpace")
    argv = ["wiki", "space", "list", "--type", space_type, "--limit", str(limit)]
    _append_optional_flags(argv, args, {"page_token": "--page-token"})
    return _run_dws(argv)


DINGTALK_WIKI_SPACE_GET_SCHEMA = {
    "name": "dingtalk_wiki_space_get",
    "description": "Get DingTalk wiki space details by workspace ID or URL. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "Wiki workspace ID or URL."}},
        "required": ["id"],
    },
}


def _handle_wiki_space_get(args: dict, **kwargs) -> str:
    wiki_id = str(args.get("id") or "").strip()
    if not wiki_id:
        return tool_error("id is required")
    return _run_dws(["wiki", "space", "get", "--id", wiki_id])


DINGTALK_DRIVE_SPACE_LIST_SCHEMA = {
    "name": "dingtalk_drive_space_list",
    "description": "List DingTalk drive spaces. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "max": {"type": "integer", "description": "Max results.", "default": 20},
            "cursor": {"type": "string", "description": "Pagination cursor."},
            "space_type": {"type": "string", "description": "Drive space type."},
        },
        "required": [],
    },
}


def _handle_drive_space_list(args: dict, **kwargs) -> str:
    max_results = _bounded_int(args.get("max"), 20, 1, 100)
    argv = ["drive", "list-spaces", "--max", str(max_results)]
    _append_optional_flags(argv, args, {"cursor": "--cursor", "space_type": "--space-type"})
    return _run_dws(argv)


DINGTALK_DRIVE_FILE_LIST_SCHEMA = {
    "name": "dingtalk_drive_file_list",
    "description": "List DingTalk drive files in a space or folder. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "space_id": {"type": "string", "description": "Drive space ID."},
            "parent_id": {"type": "string", "description": "Parent folder ID."},
            "max": {"type": "integer", "description": "Max results.", "default": 20},
            "next_token": {"type": "string", "description": "Pagination token."},
            "order": {"type": "string", "description": "Sort order."},
            "order_by": {"type": "string", "description": "Sort field."},
            "thumbnail": {"type": "string", "description": "Whether to include thumbnail."},
        },
        "required": ["space_id"],
    },
}


def _handle_drive_file_list(args: dict, **kwargs) -> str:
    space_id = str(args.get("space_id") or "").strip()
    if not space_id:
        return tool_error("space_id is required")
    max_results = _bounded_int(args.get("max"), 20, 1, 100)
    argv = ["drive", "list", "--space-id", space_id, "--max", str(max_results)]
    _append_optional_flags(
        argv,
        args,
        {
            "parent_id": "--parent-id",
            "next_token": "--next-token",
            "order": "--order",
            "order_by": "--order-by",
            "thumbnail": "--thumbnail",
        },
    )
    return _run_dws(argv)


DINGTALK_DRIVE_FILE_INFO_SCHEMA = {
    "name": "dingtalk_drive_file_info",
    "description": "Get DingTalk drive file metadata. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "space_id": {"type": "string", "description": "Drive space ID."},
            "file_id": {"type": "string", "description": "Drive file ID."},
        },
        "required": ["space_id", "file_id"],
    },
}


def _handle_drive_file_info(args: dict, **kwargs) -> str:
    space_id = str(args.get("space_id") or "").strip()
    file_id = str(args.get("file_id") or "").strip()
    if not space_id or not file_id:
        return tool_error("space_id and file_id are required")
    return _run_dws(["drive", "info", "--space-id", space_id, "--file-id", file_id])


DINGTALK_CHAT_SEARCH_GROUPS_SCHEMA = {
    "name": "dingtalk_chat_search_groups",
    "description": "Search DingTalk groups by keyword and return openConversationId candidates. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "Group name keyword."},
            "limit": {"type": "integer", "description": "Page size, max 50.", "default": 20},
            "cursor": {"type": "string", "description": "Pagination cursor.", "default": "0"},
        },
        "required": ["keyword"],
    },
}


def _handle_chat_search_groups(args: dict, **kwargs) -> str:
    keyword = str(args.get("keyword") or "").strip()
    if not keyword:
        return tool_error("keyword is required")
    limit = _bounded_int(args.get("limit"), 20, 1, 50)
    cursor = str(args.get("cursor") or "0")
    return _run_dws([
        "chat", "search",
        "--keyword", keyword,
        "--limit", str(limit),
        "--cursor", cursor,
    ])


DINGTALK_CHAT_LIST_GROUP_MESSAGES_SCHEMA = {
    "name": "dingtalk_chat_list_group_messages",
    "description": (
        "Read recent DingTalk group messages by openConversationId. Read-only. "
        "Use dingtalk_chat_search_groups first if only a group name is known."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "group": {"type": "string", "description": "DingTalk group openConversationId."},
            "time": {"type": "string", "description": "Anchor time accepted by dws chat message list."},
            "limit": {"type": "integer", "description": "Message limit, max 100.", "default": 50},
            "forward": {"type": "boolean", "description": "Whether to page forward from time.", "default": True},
        },
        "required": ["group"],
    },
}


def _handle_chat_list_group_messages(args: dict, **kwargs) -> str:
    group = str(args.get("group") or "").strip()
    if not group:
        return tool_error("group openConversationId is required")
    limit = _bounded_int(args.get("limit"), 50, 1, 100)
    argv = ["chat", "message", "list", "--group", group, "--limit", str(limit)]
    if args.get("time"):
        argv.extend(["--time", str(args["time"])])
    if args.get("forward") is not None:
        argv.extend(["--forward", str(bool(args.get("forward"))).lower()])
    return _run_dws(argv)


DINGTALK_CHAT_LIST_MESSAGES_BY_TIME_RANGE_SCHEMA = {
    "name": "dingtalk_chat_list_messages_by_time_range",
    "description": (
        "Read DingTalk chat messages in a time range. The dws result can include both "
        "single chats and group chats; filter by group_id/openConversationId in the result "
        "when needed. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "start": {"type": "string", "description": "Start time, format yyyy-MM-dd HH:mm:ss."},
            "end": {"type": "string", "description": "End time, format yyyy-MM-dd HH:mm:ss."},
            "limit": {"type": "integer", "description": "Page size, max 100.", "default": 50},
            "cursor": {"type": "string", "description": "Pagination cursor, first page is 0.", "default": "0"},
        },
        "required": ["start", "end"],
    },
}


def _handle_chat_list_messages_by_time_range(args: dict, **kwargs) -> str:
    start = str(args.get("start") or "").strip()
    end = str(args.get("end") or "").strip()
    if not start or not end:
        return tool_error("start and end are required")
    limit = _bounded_int(args.get("limit"), 50, 1, 100)
    cursor = str(args.get("cursor") or "0")
    return _run_dws([
        "chat", "message", "list-all",
        "--start", start,
        "--end", end,
        "--limit", str(limit),
        "--cursor", cursor,
    ])


DINGTALK_CONTACT_USER_SEARCH_SCHEMA = {
    "name": "dingtalk_contact_user_search",
    "description": "Search DingTalk contacts by name or keyword to resolve userId before creating todos. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "User name or keyword."},
        },
        "required": ["query"],
    },
}


def _handle_contact_user_search(args: dict, **kwargs) -> str:
    query = str(args.get("query") or "").strip()
    if not query:
        return tool_error("query is required")
    return _run_dws(["contact", "user", "search", "--query", query])


registry.register(
    name="dingtalk_auth_status",
    toolset="dingtalk_workspace",
    schema=DINGTALK_AUTH_STATUS_SCHEMA,
    handler=_handle_auth_status,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_AUTH_STATUS_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_doc_search",
    toolset="dingtalk_workspace",
    schema=DINGTALK_DOC_SEARCH_SCHEMA,
    handler=_handle_doc_search,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_DOC_SEARCH_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_doc_read",
    toolset="dingtalk_workspace",
    schema=DINGTALK_DOC_READ_SCHEMA,
    handler=_handle_doc_read,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_DOC_READ_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_doc_info",
    toolset="dingtalk_workspace",
    schema=DINGTALK_DOC_INFO_SCHEMA,
    handler=_handle_doc_info,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_DOC_INFO_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_wiki_space_search",
    toolset="dingtalk_workspace",
    schema=DINGTALK_WIKI_SPACE_SEARCH_SCHEMA,
    handler=_handle_wiki_space_search,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_WIKI_SPACE_SEARCH_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_wiki_space_list",
    toolset="dingtalk_workspace",
    schema=DINGTALK_WIKI_SPACE_LIST_SCHEMA,
    handler=_handle_wiki_space_list,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_WIKI_SPACE_LIST_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_wiki_space_get",
    toolset="dingtalk_workspace",
    schema=DINGTALK_WIKI_SPACE_GET_SCHEMA,
    handler=_handle_wiki_space_get,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_WIKI_SPACE_GET_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_drive_space_list",
    toolset="dingtalk_workspace",
    schema=DINGTALK_DRIVE_SPACE_LIST_SCHEMA,
    handler=_handle_drive_space_list,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_DRIVE_SPACE_LIST_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_drive_file_list",
    toolset="dingtalk_workspace",
    schema=DINGTALK_DRIVE_FILE_LIST_SCHEMA,
    handler=_handle_drive_file_list,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_DRIVE_FILE_LIST_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_drive_file_info",
    toolset="dingtalk_workspace",
    schema=DINGTALK_DRIVE_FILE_INFO_SCHEMA,
    handler=_handle_drive_file_info,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_DRIVE_FILE_INFO_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_chat_search_groups",
    toolset="dingtalk_workspace",
    schema=DINGTALK_CHAT_SEARCH_GROUPS_SCHEMA,
    handler=_handle_chat_search_groups,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_CHAT_SEARCH_GROUPS_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_chat_list_group_messages",
    toolset="dingtalk_workspace",
    schema=DINGTALK_CHAT_LIST_GROUP_MESSAGES_SCHEMA,
    handler=_handle_chat_list_group_messages,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_CHAT_LIST_GROUP_MESSAGES_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_chat_list_messages_by_time_range",
    toolset="dingtalk_workspace",
    schema=DINGTALK_CHAT_LIST_MESSAGES_BY_TIME_RANGE_SCHEMA,
    handler=_handle_chat_list_messages_by_time_range,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_CHAT_LIST_MESSAGES_BY_TIME_RANGE_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="dingtalk_contact_user_search",
    toolset="dingtalk_workspace",
    schema=DINGTALK_CONTACT_USER_SEARCH_SCHEMA,
    handler=_handle_contact_user_search,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_CONTACT_USER_SEARCH_SCHEMA.get("description", ""),
    emoji="📎",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)
