# -*- coding: utf-8 -*-
import json
import logging
import os
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Optional, Union, List
from urllib.parse import urlparse

from agentscope.message import Msg
from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    FunctionCall,
    FunctionCallOutput,
    MessageType,
)
from agentscope_runtime.engine.helpers.agent_api_builder import ResponseBuilder
from ...local_models.tag_parser import (
    extract_thinking_from_text,
    text_contains_think_tag,
)

logger = logging.getLogger(__name__)

_SAFE_REME_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _is_utf8_safe(text: str) -> bool:
    try:
        text.encode("utf-8")
        return True
    except UnicodeEncodeError:
        return False


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _normalize_ascii_name(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", errors="ignore").decode("ascii")
    ascii_text = _SAFE_REME_NAME_RE.sub("_", ascii_text).strip("._-")
    return ascii_text


def _decode_surrogate_name(raw_name: str) -> str | None:
    raw_bytes = os.fsencode(raw_name)
    for encoding in ("gb18030", "gbk", "big5"):
        try:
            decoded = raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
        if _is_utf8_safe(decoded):
            return decoded
    return None


def _to_pinyin_if_possible(text: str) -> str | None:
    try:
        from pypinyin import lazy_pinyin
    except ImportError:
        return None

    parts = [
        _normalize_ascii_name(piece)
        for piece in lazy_pinyin(text, errors="ignore")
    ]
    parts = [piece for piece in parts if piece]
    if not parts:
        return None
    return "_".join(parts)


def _build_safe_reme_name(path: Path) -> str:
    suffix = "".join(path.suffixes)
    stem = path.name[: -len(suffix)] if suffix else path.name
    decoded_stem = _decode_surrogate_name(stem) if not _is_utf8_safe(stem) else stem

    candidate_stem = ""
    if decoded_stem and _contains_cjk(decoded_stem):
        candidate_stem = _to_pinyin_if_possible(decoded_stem) or ""

    if not candidate_stem and decoded_stem and _is_utf8_safe(decoded_stem):
        candidate_stem = _normalize_ascii_name(decoded_stem)

    if not candidate_stem:
        candidate_stem = f"md_{uuid.uuid4().hex[:12]}"

    candidate_stem = candidate_stem.strip("._-") or f"md_{uuid.uuid4().hex[:12]}"
    return f"{candidate_stem}{suffix}"


def _dedupe_path(parent: Path, candidate_name: str) -> Path:
    candidate = parent / candidate_name
    if not candidate.exists():
        return candidate

    suffix = "".join(candidate.suffixes)
    stem = (
        candidate_name[: -len(suffix)] if suffix else candidate_name
    ).rstrip("._-") or f"md_{uuid.uuid4().hex[:8]}"
    for idx in range(1, 1000):
        deduped = parent / f"{stem}_{idx}{suffix}"
        if not deduped.exists():
            return deduped

    return parent / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"


def _iter_reme_paths(working_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for filename in ("MEMORY.md", "memory.md"):
        path = working_dir / filename
        if path.exists():
            candidates.append(path)

    memory_dir = working_dir / "memory"
    if memory_dir.exists():
        files = [path for path in memory_dir.rglob("*.md") if path.is_file()]
        directories = sorted(
            [path for path in memory_dir.rglob("*") if path.is_dir()],
            key=lambda p: len(p.parts),
            reverse=True,
        )
        candidates.extend(files)
        candidates.extend(directories)
    return candidates


def ensure_reme_safe_markdown_paths(
    working_dir: Path,
) -> list[tuple[Path, Path]]:
    """Rename ReMe-scanned paths whose names cannot be UTF-8 encoded.

    ReMe hashes source metadata using ``text.encode("utf-8")`` and will crash
    if any path segment contains surrogate escapes. This helper only touches
    the memory files/directories that ReMe is expected to watch.
    """
    renamed: list[tuple[Path, Path]] = []
    for path in _iter_reme_paths(working_dir):
        if _is_utf8_safe(path.name):
            continue

        new_name = _build_safe_reme_name(path)
        new_path = _dedupe_path(path.parent, new_name)
        path.rename(new_path)
        renamed.append((path, new_path))
        logger.warning(
            "Renamed ReMe-scanned path with invalid UTF-8 name: %r -> %s",
            str(path),
            new_path,
        )

    return renamed


def build_env_context(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    channel: Optional[str] = None,
    working_dir: Optional[str] = None,
    add_hint: bool = True,
) -> str:
    """
    Build environment context with current request context prepended.

    Args:
        session_id: Current session ID
        user_id: Current user ID
        channel: Current channel name
        working_dir: Working directory path
        add_hint: Whether to add hint context
    Returns:
        Formatted environment context string
    """
    parts = []
    if session_id is not None:
        parts.append(f"- 当前的session_id: {session_id}")
    if user_id is not None:
        parts.append(f"- 当前的user_id: {user_id}")
    if channel is not None:
        parts.append(f"- 当前的channel: {channel}")

    if working_dir is not None:
        parts.append(f"- 工作目录: {working_dir}")

    if add_hint:
        parts.append(
            "- 重要提示:\n"
            "  1. 完成任务时，优先考虑使用 skills"
            "（例如定时任务，优先使用 cron skill）。"
            "对于不清楚的 skills，请先查阅相关对应文档。\n"
            "  2. 使用 write_file 写文件时，如果担心覆盖原有内容，"
            "可以先用 read_file 查看文件内容，"
            "再使用 edit_file 工具进行局部内容更新或追加内容。",
        )

    return (
        "====================\n" + "\n".join(parts) + "\n===================="
    )


# pylint: disable=too-many-branches,too-many-statements
def agentscope_msg_to_message(
    messages: Union[Msg, List[Msg]],
) -> List[Message]:
    """
    Convert AgentScope Msg(s) into one or more runtime Message objects

    Args:
        messages: AgentScope message(s) from streaming.

    Returns:
        List[Message]: One or more constructed runtime Message objects.
    """
    if isinstance(messages, Msg):
        msgs = [messages]
    elif isinstance(messages, list):
        msgs = messages
    else:
        raise TypeError(f"Expected Msg or list[Msg], got {type(messages)}")

    results: List[Message] = []

    def _append_text_and_reasoning(
        *,
        role: str,
        text: str,
        metadata: dict,
    ) -> None:
        if text and text_contains_think_tag(text):
            parsed = extract_thinking_from_text(text)
            if parsed.thinking:
                rb = ResponseBuilder()
                mb = rb.create_message_builder(
                    role=role,
                    message_type=MessageType.REASONING,
                )
                mb.message.metadata = metadata
                cb = mb.create_content_builder(content_type="text")
                cb.set_text(parsed.thinking)
                cb.complete()
                mb.complete()
                results.append(mb.get_message_data())

            if parsed.remaining_text:
                rb = ResponseBuilder()
                mb = rb.create_message_builder(
                    role=role,
                    message_type=MessageType.MESSAGE,
                )
                mb.message.metadata = metadata
                cb = mb.create_content_builder(content_type="text")
                cb.set_text(parsed.remaining_text)
                cb.complete()
                mb.complete()
                results.append(mb.get_message_data())
            return

        rb = ResponseBuilder()
        mb = rb.create_message_builder(
            role=role,
            message_type=MessageType.MESSAGE,
        )
        mb.message.metadata = metadata
        cb = mb.create_content_builder(content_type="text")
        cb.set_text(text)
        cb.complete()
        mb.complete()
        results.append(mb.get_message_data())

    for msg in msgs:
        role = msg.role or "assistant"
        metadata = {
            "original_id": msg.id,
            "original_name": msg.name,
            "metadata": msg.metadata,
        }

        if isinstance(msg.content, str):
            _append_text_and_reasoning(
                role=role,
                text=msg.content,
                metadata=metadata,
            )
            continue

        # msg.content is a list of blocks
        # We group blocks by high-level message type
        current_mb = None
        current_type = None

        for block in msg.content:
            if isinstance(block, dict):
                btype = block.get("type", "text")
            else:
                continue

            if btype == "text":
                # Check for thinking tags in text block
                text = block.get("text", "")
                if text_contains_think_tag(text):
                    parsed = extract_thinking_from_text(text)
                    # Add thinking content as REASONING type
                    if parsed.thinking:
                        if current_type != MessageType.REASONING:
                            if current_mb:
                                current_mb.complete()
                                results.append(current_mb.get_message_data())
                            rb = ResponseBuilder()
                            current_mb = rb.create_message_builder(
                                role=role,
                                message_type=MessageType.REASONING,
                            )
                            current_mb.message.metadata = {
                                "original_id": msg.id,
                                "original_name": msg.name,
                                "metadata": msg.metadata,
                            }
                            current_type = MessageType.REASONING
                        cb = current_mb.create_content_builder(content_type="text")
                        cb.set_text(parsed.thinking)
                        cb.complete()
                    # Add remaining text as MESSAGE type
                    if parsed.remaining_text:
                        if current_type != MessageType.MESSAGE:
                            if current_mb:
                                current_mb.complete()
                                results.append(current_mb.get_message_data())
                            rb = ResponseBuilder()
                            current_mb = rb.create_message_builder(
                                role=role,
                                message_type=MessageType.MESSAGE,
                            )
                            current_mb.message.metadata = {
                                "original_id": msg.id,
                                "original_name": msg.name,
                                "metadata": msg.metadata,
                            }
                            current_type = MessageType.MESSAGE
                        cb = current_mb.create_content_builder(content_type="text")
                        cb.set_text(parsed.remaining_text)
                        cb.complete()
                    continue
                # No thinking tags - original logic
                if current_type != MessageType.MESSAGE:
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                    rb = ResponseBuilder()
                    current_mb = rb.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    # add meta field to store old id and name
                    current_mb.message.metadata = metadata
                    current_type = MessageType.MESSAGE
                text = block.get("text", "")
                if text and text_contains_think_tag(text):
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                        current_mb = None
                        current_type = None
                    _append_text_and_reasoning(
                        role=role,
                        text=text,
                        metadata=metadata,
                    )
                    continue

                cb = current_mb.create_content_builder(content_type="text")
                cb.set_text(text)
                cb.complete()

            elif btype == "thinking":
                # Create/continue REASONING type
                if current_type != MessageType.REASONING:
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                    rb = ResponseBuilder()
                    current_mb = rb.create_message_builder(
                        role=role,
                        message_type=MessageType.REASONING,
                    )
                    # add meta field to store old id and name
                    current_mb.message.metadata = metadata
                    current_type = MessageType.REASONING
                cb = current_mb.create_content_builder(content_type="text")
                cb.set_text(block.get("thinking", ""))
                cb.complete()

            elif btype == "tool_use":
                # Always start a new PLUGIN_CALL message
                if current_mb:
                    current_mb.complete()
                    results.append(current_mb.get_message_data())
                rb = ResponseBuilder()
                current_mb = rb.create_message_builder(
                    role=role,
                    message_type=MessageType.PLUGIN_CALL,
                )
                # add meta field to store old id and name
                current_mb.message.metadata = metadata
                current_type = MessageType.PLUGIN_CALL
                cb = current_mb.create_content_builder(content_type="data")

                if isinstance(block.get("input"), (dict, list)):
                    arguments = json.dumps(
                        block.get("input"),
                        ensure_ascii=False,
                    )
                else:
                    arguments = block.get("input")

                call_data = FunctionCall(
                    call_id=block.get("id"),
                    name=block.get("name"),
                    arguments=arguments,
                ).model_dump()
                cb.set_data(call_data)
                cb.complete()

            elif btype == "tool_result":
                # Always start a new PLUGIN_CALL_OUTPUT message
                if current_mb:
                    current_mb.complete()
                    results.append(current_mb.get_message_data())
                rb = ResponseBuilder()
                current_mb = rb.create_message_builder(
                    role=role,
                    message_type=MessageType.PLUGIN_CALL_OUTPUT,
                )
                # add meta field to store old id and name
                current_mb.message.metadata = metadata
                current_type = MessageType.PLUGIN_CALL_OUTPUT
                cb = current_mb.create_content_builder(content_type="data")

                if isinstance(block.get("output"), (dict, list)):
                    output = json.dumps(
                        block.get("output"),
                        ensure_ascii=False,
                    )
                else:
                    output = block.get("output")

                output_data = FunctionCallOutput(
                    call_id=block.get("id"),
                    name=block.get("name"),
                    output=output,
                ).model_dump(exclude_none=True)
                cb.set_data(output_data)
                cb.complete()

            elif btype == "image":
                # Create/continue MESSAGE type with image
                if current_type != MessageType.MESSAGE:
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                    rb = ResponseBuilder()
                    current_mb = rb.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    # add meta field to store old id and name
                    current_mb.message.metadata = metadata
                    current_type = MessageType.MESSAGE
                cb = current_mb.create_content_builder(content_type="image")

                if (
                    isinstance(block.get("source"), dict)
                    and block.get("source", {}).get("type") == "url"
                ):
                    cb.set_image_url(block.get("source", {}).get("url"))

                elif (
                    isinstance(block.get("source"), dict)
                    and block.get("source").get(
                        "type",
                    )
                    == "base64"
                ):
                    media_type = block.get("source", {}).get(
                        "media_type",
                        "image/jpeg",
                    )
                    base64_data = block.get("source", {}).get("data", "")
                    url = f"data:{media_type};base64,{base64_data}"
                    cb.set_image_url(url)

                cb.complete()

            elif btype == "audio":
                # Create/continue MESSAGE type with audio
                if current_type != MessageType.MESSAGE:
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                    rb = ResponseBuilder()
                    current_mb = rb.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    # add meta field to store old id and name
                    current_mb.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.MESSAGE
                cb = current_mb.create_content_builder(content_type="audio")
                # URLSource runtime check (dict with type == "url")
                if (
                    isinstance(block.get("source"), dict)
                    and block.get("source", {}).get(
                        "type",
                    )
                    == "url"
                ):
                    url = block.get("source", {}).get("url")
                    cb.content.data = url
                    try:
                        cb.content.format = urlparse(url).path.split(".")[-1]
                    except (AttributeError, IndexError, ValueError):
                        cb.content.format = None

                # Base64Source runtime check (dict with type == "base64")
                elif (
                    isinstance(block.get("source"), dict)
                    and block.get("source").get(
                        "type",
                    )
                    == "base64"
                ):
                    media_type = block.get("source", {}).get(
                        "media_type",
                    )
                    base64_data = block.get("source", {}).get("data", "")
                    url = f"data:{media_type};base64,{base64_data}"

                    cb.content.data = url
                    cb.content.format = media_type

                cb.complete()

            else:
                # Fallback to MESSAGE type
                if current_type != MessageType.MESSAGE:
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                    rb = ResponseBuilder()
                    current_mb = rb.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    # add meta field to store old id and name
                    current_mb.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.MESSAGE
                cb = current_mb.create_content_builder(content_type="text")
                cb.set_text(str(block))
                cb.complete()

        # finalize last open message builder
        if current_mb:
            current_mb.complete()
            results.append(current_mb.get_message_data())

    return results
