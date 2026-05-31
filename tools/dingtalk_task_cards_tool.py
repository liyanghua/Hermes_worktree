"""Local DingTalk task-card previews and todo creation helpers.

Task-card previews are stored in Hermes home as JSONL so chat-derived action
items can be reviewed before any DingTalk write operation happens. Creating a
DingTalk todo is explicit and updates the local preview after dws succeeds.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home
from tools.dingtalk_workspace_tool import _check_dws, _parse_json_maybe, _run_dws
from tools.registry import registry, tool_error, tool_result


_MAX_RESULT_SIZE_CHARS = 200_000
_STORE_NAME = "dingtalk_task_cards.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _store_path() -> Path:
    home = get_hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    return home / _STORE_NAME


def _read_cards() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    cards: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("id"):
                cards.append(value)
    return cards


def _write_cards(cards: list[dict[str, Any]]) -> None:
    path = _store_path()
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as fh:
        for card in cards:
            fh.write(json.dumps(card, ensure_ascii=False, sort_keys=True) + "\n")
    temp_path.replace(path)


def _find_card(cards: list[dict[str, Any]], card_id: str) -> tuple[int, dict[str, Any] | None]:
    for index, card in enumerate(cards):
        if card.get("id") == card_id:
            return index, card
    return -1, None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_card(args: dict[str, Any]) -> dict[str, Any]:
    source = args.get("source") if isinstance(args.get("source"), dict) else {}
    group_id = str(args.get("group_id") or source.get("group_id") or "").strip()
    title = str(args.get("title") or "").strip()
    summary = str(args.get("summary") or "").strip()
    if not group_id:
        raise ValueError("group_id is required")
    if not title:
        raise ValueError("title is required")
    if not summary:
        raise ValueError("summary is required")

    now = _now_iso()
    return {
        "id": str(args.get("id") or f"dtc_{uuid.uuid4().hex[:12]}"),
        "group_id": group_id,
        "source": {
            "start": str(source.get("start") or args.get("start") or ""),
            "end": str(source.get("end") or args.get("end") or ""),
            "message_ids": [str(item) for item in _as_list(source.get("message_ids") or args.get("message_ids"))],
        },
        "title": title,
        "summary": summary,
        "owner_hint": str(args.get("owner_hint") or ""),
        "executor_user_ids": [str(item) for item in _as_list(args.get("executor_user_ids"))],
        "due": str(args.get("due") or ""),
        "priority": str(args.get("priority") or "20"),
        "evidence": [str(item) for item in _as_list(args.get("evidence"))],
        "status": str(args.get("status") or "preview"),
        "dingtalk_todo_id": args.get("dingtalk_todo_id"),
        "dingtalk_todo_result": args.get("dingtalk_todo_result"),
        "created_at": str(args.get("created_at") or now),
        "updated_at": now,
    }


DINGTALK_TASK_CARD_SAVE_PREVIEW_SCHEMA = {
    "name": "dingtalk_task_card_save_preview",
    "description": "Save a local DingTalk group task-card preview. This does not create DingTalk todos.",
    "parameters": {
        "type": "object",
        "properties": {
            "group_id": {"type": "string", "description": "DingTalk group openConversationId."},
            "title": {"type": "string", "description": "Task card title."},
            "summary": {"type": "string", "description": "Context summary for the task."},
            "owner_hint": {"type": "string", "description": "Potential owner name/userId inferred from chat."},
            "executor_user_ids": {"type": "array", "items": {"type": "string"}},
            "due": {"type": "string", "description": "Due time ISO-8601, optional."},
            "priority": {"type": "string", "description": "10=low, 20=normal, 30=high, 40=urgent."},
            "evidence": {"type": "array", "items": {"type": "string"}, "description": "Key message excerpts."},
            "source": {
                "type": "object",
                "properties": {
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "message_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "required": ["group_id", "title", "summary"],
    },
}


def _handle_save_preview(args: dict, **kwargs) -> str:
    try:
        card = _normalize_card(args)
    except ValueError as exc:
        return tool_error(str(exc))
    cards = _read_cards()
    if any(existing.get("id") == card["id"] for existing in cards):
        return tool_error("task card id already exists", id=card["id"])
    cards.append(card)
    _write_cards(cards)
    return tool_result(success=True, card=card, store=str(_store_path()))


DINGTALK_TASK_CARD_LIST_PREVIEWS_SCHEMA = {
    "name": "dingtalk_task_card_list_previews",
    "description": "List local DingTalk task-card previews, optionally filtered by group_id and status.",
    "parameters": {
        "type": "object",
        "properties": {
            "group_id": {"type": "string", "description": "Filter by DingTalk group openConversationId."},
            "status": {"type": "string", "description": "Filter by preview or created."},
            "limit": {"type": "integer", "default": 20},
        },
        "required": [],
    },
}


def _handle_list_previews(args: dict, **kwargs) -> str:
    group_id = str(args.get("group_id") or "").strip()
    status = str(args.get("status") or "").strip()
    try:
        limit = int(args.get("limit") or 20)
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(100, limit))
    cards = _read_cards()
    if group_id:
        cards = [card for card in cards if card.get("group_id") == group_id]
    if status:
        cards = [card for card in cards if card.get("status") == status]
    cards = sorted(cards, key=lambda card: str(card.get("updated_at") or card.get("created_at") or ""), reverse=True)
    return tool_result(success=True, count=len(cards[:limit]), cards=cards[:limit], store=str(_store_path()))


DINGTALK_TASK_CARD_GET_PREVIEW_SCHEMA = {
    "name": "dingtalk_task_card_get_preview",
    "description": "Get one local DingTalk task-card preview by id.",
    "parameters": {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "Local task card id."}},
        "required": ["id"],
    },
}


def _handle_get_preview(args: dict, **kwargs) -> str:
    card_id = str(args.get("id") or "").strip()
    if not card_id:
        return tool_error("id is required")
    _, card = _find_card(_read_cards(), card_id)
    if not card:
        return tool_error("task card not found", id=card_id)
    return tool_result(success=True, card=card)


DINGTALK_TASK_CARD_UPDATE_PREVIEW_SCHEMA = {
    "name": "dingtalk_task_card_update_preview",
    "description": "Update a local DingTalk task-card preview before creating a DingTalk todo.",
    "parameters": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Local task card id."},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "owner_hint": {"type": "string"},
            "executor_user_ids": {"type": "array", "items": {"type": "string"}},
            "due": {"type": "string"},
            "priority": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["id"],
    },
}


def _handle_update_preview(args: dict, **kwargs) -> str:
    card_id = str(args.get("id") or "").strip()
    if not card_id:
        return tool_error("id is required")
    cards = _read_cards()
    index, card = _find_card(cards, card_id)
    if not card:
        return tool_error("task card not found", id=card_id)
    for key in ("title", "summary", "owner_hint", "due", "priority"):
        if key in args and args[key] is not None:
            card[key] = str(args[key])
    for key in ("executor_user_ids", "evidence"):
        if key in args and args[key] is not None:
            card[key] = [str(item) for item in _as_list(args[key])]
    card["updated_at"] = _now_iso()
    cards[index] = card
    _write_cards(cards)
    return tool_result(success=True, card=card)


DINGTALK_TASK_CARD_CREATE_TODO_SCHEMA = {
    "name": "dingtalk_task_card_create_todo",
    "description": (
        "Create a DingTalk todo from a local task-card preview using dws todo task create. "
        "This writes to DingTalk and should only be used after explicit user confirmation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Local task card id."},
            "executor_user_ids": {"type": "array", "items": {"type": "string"}, "description": "Confirmed DingTalk userIds."},
            "due": {"type": "string", "description": "Due time ISO-8601."},
            "priority": {"type": "string", "description": "10=low, 20=normal, 30=high, 40=urgent."},
            "title": {"type": "string", "description": "Override todo title."},
        },
        "required": ["id", "executor_user_ids"],
    },
}


def _handle_create_todo(args: dict, **kwargs) -> str:
    card_id = str(args.get("id") or "").strip()
    if not card_id:
        return tool_error("id is required")
    executor_user_ids = [str(item).strip() for item in _as_list(args.get("executor_user_ids")) if str(item).strip()]
    if not executor_user_ids:
        return tool_error("executor_user_ids is required")

    cards = _read_cards()
    index, card = _find_card(cards, card_id)
    if not card:
        return tool_error("task card not found", id=card_id)

    title = str(args.get("title") or card.get("title") or "").strip()
    if not title:
        return tool_error("title is required")
    due = str(args.get("due") or card.get("due") or "").strip()
    priority = str(args.get("priority") or card.get("priority") or "20").strip()

    argv = [
        "todo", "task", "create",
        "--title", title,
        "--executors", ",".join(executor_user_ids),
        "--priority", priority,
        "--yes",
    ]
    if due:
        argv.extend(["--due", due])

    raw_result = _run_dws(argv, timeout=120)
    parsed_result = _parse_json_maybe(raw_result)
    if isinstance(parsed_result, dict) and parsed_result.get("error"):
        return raw_result

    card["executor_user_ids"] = executor_user_ids
    card["due"] = due
    card["priority"] = priority
    card["status"] = "created"
    card["dingtalk_todo_result"] = parsed_result
    if isinstance(parsed_result, dict):
        stdout = parsed_result.get("stdout")
        if isinstance(stdout, dict):
            card["dingtalk_todo_id"] = stdout.get("id") or stdout.get("taskId") or stdout.get("todoId")
    card["updated_at"] = _now_iso()
    cards[index] = card
    _write_cards(cards)
    return tool_result(success=True, card=card, dws_result=parsed_result)


registry.register(
    name="dingtalk_task_card_save_preview",
    toolset="dingtalk_workspace",
    schema=DINGTALK_TASK_CARD_SAVE_PREVIEW_SCHEMA,
    handler=_handle_save_preview,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_TASK_CARD_SAVE_PREVIEW_SCHEMA.get("description", ""),
    emoji="📋",
    max_result_size_chars=_MAX_RESULT_SIZE_CHARS,
)

registry.register(
    name="dingtalk_task_card_list_previews",
    toolset="dingtalk_workspace",
    schema=DINGTALK_TASK_CARD_LIST_PREVIEWS_SCHEMA,
    handler=_handle_list_previews,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_TASK_CARD_LIST_PREVIEWS_SCHEMA.get("description", ""),
    emoji="📋",
    max_result_size_chars=_MAX_RESULT_SIZE_CHARS,
)

registry.register(
    name="dingtalk_task_card_get_preview",
    toolset="dingtalk_workspace",
    schema=DINGTALK_TASK_CARD_GET_PREVIEW_SCHEMA,
    handler=_handle_get_preview,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_TASK_CARD_GET_PREVIEW_SCHEMA.get("description", ""),
    emoji="📋",
    max_result_size_chars=_MAX_RESULT_SIZE_CHARS,
)

registry.register(
    name="dingtalk_task_card_update_preview",
    toolset="dingtalk_workspace",
    schema=DINGTALK_TASK_CARD_UPDATE_PREVIEW_SCHEMA,
    handler=_handle_update_preview,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_TASK_CARD_UPDATE_PREVIEW_SCHEMA.get("description", ""),
    emoji="📋",
    max_result_size_chars=_MAX_RESULT_SIZE_CHARS,
)

registry.register(
    name="dingtalk_task_card_create_todo",
    toolset="dingtalk_workspace",
    schema=DINGTALK_TASK_CARD_CREATE_TODO_SCHEMA,
    handler=_handle_create_todo,
    check_fn=_check_dws,
    requires_env=[],
    is_async=False,
    description=DINGTALK_TASK_CARD_CREATE_TODO_SCHEMA.get("description", ""),
    emoji="📋",
    max_result_size_chars=_MAX_RESULT_SIZE_CHARS,
)