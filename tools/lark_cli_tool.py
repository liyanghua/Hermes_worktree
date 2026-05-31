"""Read-only lark-cli bridge tools for Feishu/Lark Drive, Docs, and Wiki.

These tools intentionally expose only read/search operations.  They delegate
authentication, scope handling, pagination semantics, and token storage to the
official ``lark-cli`` maintained by LarkSuite.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any

from tools.registry import registry, tool_error, tool_result


_LARK_CLI_BIN = "lark-cli"
_DEFAULT_TIMEOUT_SECONDS = 60
_MAX_STDOUT_CHARS = 200_000
_WIKI_TOKEN_RE = re.compile(r"/(?:wiki)/([^/?#]+)")


def _check_lark_cli() -> bool:
    return shutil.which(_LARK_CLI_BIN) is not None


def _parse_json_maybe(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _run_lark_cli(argv: list[str], timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> str:
    if not _check_lark_cli():
        return tool_error(
            "lark-cli is not installed. Install with: npx @larksuite/cli@latest install",
            setup={
                "install": "npx @larksuite/cli@latest install",
                "config": "lark-cli config init --new",
                "login": "lark-cli auth login --recommend",
            },
        )

    try:
        completed = subprocess.run(
            [_LARK_CLI_BIN, *argv],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return tool_error("lark-cli command timed out", argv=[_LARK_CLI_BIN, *argv])

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    parsed_stdout = _parse_json_maybe(stdout[:_MAX_STDOUT_CHARS])
    parsed_stderr = _parse_json_maybe(stderr)

    if completed.returncode != 0:
        hint = {
            "auth_status": "lark-cli auth status",
            "login_recommended": "lark-cli auth login --recommend",
            "login_search_scope": "lark-cli auth login --scope 'search:docs:read'",
        }
        return tool_error(
            "lark-cli command failed",
            code=completed.returncode,
            argv=[_LARK_CLI_BIN, *argv],
            stdout=parsed_stdout,
            stderr=parsed_stderr,
            hint=hint,
        )

    return tool_result(
        success=True,
        argv=[_LARK_CLI_BIN, *argv],
        stdout=parsed_stdout,
        stderr=parsed_stderr,
    )


def _extract_wiki_token(value: str) -> str:
    value = (value or "").strip()
    match = _WIKI_TOKEN_RE.search(value)
    return match.group(1) if match else value


LARK_AUTH_STATUS_SCHEMA = {
    "name": "lark_auth_status",
    "description": "Check whether lark-cli is configured and logged in for Feishu/Lark access.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def _handle_auth_status(args: dict, **kwargs) -> str:
    return _run_lark_cli(["auth", "status"], timeout=30)


LARK_DRIVE_SEARCH_SCHEMA = {
    "name": "lark_drive_search",
    "description": (
        "Search Feishu/Lark Drive and Wiki resources using the official lark-cli. "
        "Use this to find documents, knowledge-base nodes, sheets, and files. "
        "Read-only; runs as the logged-in user."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keywords. Use empty string for filter-only browsing.",
                "default": "",
            },
            "page_size": {
                "type": "integer",
                "description": "Results per page, max 20.",
                "default": 10,
            },
            "page_token": {"type": "string", "description": "Pagination token from a previous result."},
            "doc_types": {
                "type": "string",
                "description": "Comma-separated types such as docx,wiki,sheet,bitable,folder,file.",
            },
            "space_ids": {"type": "string", "description": "Comma-separated wiki space IDs to restrict search."},
            "mine": {"type": "boolean", "description": "Only search resources owned by the current user."},
            "edited_since": {"type": "string", "description": "Relative or absolute time, e.g. 7d, 1m, 2026-04-01."},
            "opened_since": {"type": "string", "description": "Relative or absolute open-time filter, e.g. 7d."},
            "sort": {
                "type": "string",
                "description": "Sort value: default, edit_time, edit_time_asc, open_time, create_time.",
            },
        },
        "required": [],
    },
}


def _handle_drive_search(args: dict, **kwargs) -> str:
    page_size = max(1, min(20, int(args.get("page_size") or 10)))
    argv = [
        "drive",
        "+search",
        "--as",
        "user",
        "--format",
        "json",
        "--query",
        str(args.get("query") or ""),
        "--page-size",
        str(page_size),
    ]
    optional_flags = {
        "page_token": "--page-token",
        "doc_types": "--doc-types",
        "space_ids": "--space-ids",
        "edited_since": "--edited-since",
        "opened_since": "--opened-since",
        "sort": "--sort",
    }
    for key, flag in optional_flags.items():
        value = args.get(key)
        if value:
            argv.extend([flag, str(value)])
    if args.get("mine"):
        argv.append("--mine")
    return _run_lark_cli(argv)


LARK_DOC_FETCH_SCHEMA = {
    "name": "lark_doc_fetch",
    "description": (
        "Read a Feishu/Lark document or Wiki-backed document as structured content via "
        "lark-cli docs +fetch --api-version v2. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "doc": {"type": "string", "description": "Document URL or token."},
            "scope": {
                "type": "string",
                "description": "Fetch scope if supported by lark-cli, e.g. all or selection-specific values.",
            },
            "detail": {
                "type": "string",
                "description": "Detail mode if supported by lark-cli, e.g. with-ids.",
            },
            "doc_format": {
                "type": "string",
                "description": "Output document format, typically xml or markdown if supported.",
            },
        },
        "required": ["doc"],
    },
}


def _handle_doc_fetch(args: dict, **kwargs) -> str:
    doc = (args.get("doc") or "").strip()
    if not doc:
        return tool_error("doc is required")
    argv = [
        "docs",
        "+fetch",
        "--as",
        "user",
        "--api-version",
        "v2",
        "--doc",
        doc,
        "--format",
        "json",
    ]
    optional_flags = {
        "scope": "--scope",
        "detail": "--detail",
        "doc_format": "--doc-format",
    }
    for key, flag in optional_flags.items():
        value = args.get(key)
        if value:
            argv.extend([flag, str(value)])
    return _run_lark_cli(argv, timeout=120)


LARK_WIKI_GET_NODE_SCHEMA = {
    "name": "lark_wiki_get_node",
    "description": "Get Feishu/Lark Wiki node metadata by wiki URL or wiki token. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "wiki": {"type": "string", "description": "Wiki URL or wiki token."},
        },
        "required": ["wiki"],
    },
}


def _handle_wiki_get_node(args: dict, **kwargs) -> str:
    token = _extract_wiki_token(args.get("wiki") or "")
    if not token:
        return tool_error("wiki URL or token is required")
    return _run_lark_cli([
        "wiki",
        "spaces",
        "get_node",
        "--as",
        "user",
        "--format",
        "json",
        "--params",
        json.dumps({"token": token}, ensure_ascii=False),
    ])


LARK_WIKI_LIST_SPACES_SCHEMA = {
    "name": "lark_wiki_list_spaces",
    "description": "List Feishu/Lark Wiki spaces accessible to the logged-in user. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "page_size": {"type": "integer", "description": "Page size.", "default": 20},
            "page_token": {"type": "string", "description": "Pagination token."},
        },
        "required": [],
    },
}


def _handle_wiki_list_spaces(args: dict, **kwargs) -> str:
    page_size = max(1, min(50, int(args.get("page_size") or 20)))
    params: dict[str, Any] = {"page_size": page_size}
    if args.get("page_token"):
        params["page_token"] = str(args["page_token"])
    return _run_lark_cli([
        "wiki",
        "spaces",
        "list",
        "--as",
        "user",
        "--format",
        "json",
        "--params",
        json.dumps(params, ensure_ascii=False),
    ])


registry.register(
    name="lark_auth_status",
    toolset="lark_cli",
    schema=LARK_AUTH_STATUS_SCHEMA,
    handler=_handle_auth_status,
    check_fn=_check_lark_cli,
    requires_env=[],
    is_async=False,
    description=LARK_AUTH_STATUS_SCHEMA.get("description", ""),
    emoji="📚",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="lark_drive_search",
    toolset="lark_cli",
    schema=LARK_DRIVE_SEARCH_SCHEMA,
    handler=_handle_drive_search,
    check_fn=_check_lark_cli,
    requires_env=[],
    is_async=False,
    description=LARK_DRIVE_SEARCH_SCHEMA.get("description", ""),
    emoji="📚",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="lark_doc_fetch",
    toolset="lark_cli",
    schema=LARK_DOC_FETCH_SCHEMA,
    handler=_handle_doc_fetch,
    check_fn=_check_lark_cli,
    requires_env=[],
    is_async=False,
    description=LARK_DOC_FETCH_SCHEMA.get("description", ""),
    emoji="📚",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="lark_wiki_get_node",
    toolset="lark_cli",
    schema=LARK_WIKI_GET_NODE_SCHEMA,
    handler=_handle_wiki_get_node,
    check_fn=_check_lark_cli,
    requires_env=[],
    is_async=False,
    description=LARK_WIKI_GET_NODE_SCHEMA.get("description", ""),
    emoji="📚",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)

registry.register(
    name="lark_wiki_list_spaces",
    toolset="lark_cli",
    schema=LARK_WIKI_LIST_SPACES_SCHEMA,
    handler=_handle_wiki_list_spaces,
    check_fn=_check_lark_cli,
    requires_env=[],
    is_async=False,
    description=LARK_WIKI_LIST_SPACES_SCHEMA.get("description", ""),
    emoji="📚",
    max_result_size_chars=_MAX_STDOUT_CHARS,
)