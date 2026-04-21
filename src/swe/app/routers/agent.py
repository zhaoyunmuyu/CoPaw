# -*- coding: utf-8 -*-
"""Agent file management API."""
# pylint: disable=no-name-in-module
import json
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ..utils import schedule_agent_reload
from ...config import (
    load_config,
    save_config,
    AgentsRunningConfig,
)
from ...config.config import save_agent_config
from ...agents.memory.agent_md_manager import AgentMdManager
from ...agents.utils import copy_builtin_qa_md_files, copy_md_files
from ...constant import BUILTIN_QA_AGENT_ID
from ..agent_context import (
    get_agent_for_request,
    get_agent_and_config_for_request,
)

router = APIRouter(prefix="/agent", tags=["agent"])


class MdFileInfo(BaseModel):
    """Markdown file metadata."""

    filename: str = Field(..., description="File name")
    path: str = Field(..., description="File path")
    size: int = Field(..., description="Size in bytes")
    created_time: str = Field(..., description="Created time")
    modified_time: str = Field(..., description="Modified time")


class MdFileContent(BaseModel):
    """Markdown file content."""

    content: str = Field(..., description="File content")


class AgentInitRequest(BaseModel):
    """Request model for appending initialization text to a working md."""

    model_config = ConfigDict(
        populate_by_name=False,
        json_schema_extra={
            "type": "object",
            "required": ["filename", "text", "agentId"],
            "properties": {
                "filename": {
                    "type": "string",
                    "title": "Filename",
                    "description": "Top-level markdown file name",
                },
                "text": {
                    "type": "string",
                    "title": "Text",
                    "description": "Text to append",
                },
                "agentId": {
                    "type": "string",
                    "title": "Agentid",
                    "description": "Agent ID",
                },
            },
        },
    )

    filename: object = Field(None, description="Top-level markdown file name")
    text: object = Field(None, description="Text to append")
    agent_id: object = Field(None, alias="agentId", description="Agent ID")


class AgentInitResponse(BaseModel):
    """Response model for init append endpoint."""

    appended: bool = Field(..., description="Whether append succeeded")
    filename: str = Field(..., description="Resolved markdown filename")
    agent_id: str = Field(..., description="Target agent ID")


def _require_string(value: object, detail: str) -> str:
    """Require a field value to be a string for endpoint-local validation."""
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=detail)
    return value


def _normalize_top_level_md_filename(filename: str | None) -> str:
    """Validate and normalize a top-level markdown filename."""
    if filename is None or not filename.strip():
        raise HTTPException(status_code=400, detail="filename is required")

    normalized = filename.strip()
    if "/" in normalized or "\\" in normalized or ".." in normalized:
        raise HTTPException(
            status_code=400,
            detail="filename must be a top-level Markdown file name",
        )
    if any(ord(char) < 32 for char in normalized):
        raise HTTPException(
            status_code=400,
            detail="filename must be a top-level Markdown file name",
        )
    if normalized.startswith("."):
        raise HTTPException(
            status_code=400,
            detail="filename must be a top-level Markdown file name",
        )
    if normalized.endswith("."):
        raise HTTPException(
            status_code=400,
            detail="filename must be a top-level Markdown file name",
        )

    path = Path(normalized)
    if path.name != normalized:
        raise HTTPException(
            status_code=400,
            detail="filename must be a top-level Markdown file name",
        )

    suffix = path.suffix.lower()
    if suffix and suffix != ".md":
        raise HTTPException(
            status_code=400,
            detail="filename must be a top-level Markdown file name",
        )
    if not suffix:
        normalized = f"{normalized}.md"
    elif path.suffix != ".md":
        normalized = f"{path.stem}.md"
    if ".." in normalized:
        raise HTTPException(
            status_code=400,
            detail="filename must be a top-level Markdown file name",
        )

    return normalized


@router.post(
    "/init",
    response_model=AgentInitResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["filename", "text", "agentId"],
                        "properties": {
                            "filename": {"type": "string"},
                            "text": {"type": "string"},
                            "agentId": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
)
async def append_init_text(
    request: Request,
) -> dict:
    """Append initialization text to a working markdown file."""
    try:
        if "agentId" in request.path_params:
            raise HTTPException(status_code=404, detail="Not Found")

        raw_body = await request.body()
        if not raw_body:
            raise HTTPException(
                status_code=400,
                detail="request body is required",
            )

        try:
            body = json.loads(raw_body)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="request body must be a JSON object",
            ) from exc

        if not isinstance(body, dict):
            raise HTTPException(
                status_code=400,
                detail="request body must be a JSON object",
            )

        raw_filename = _require_string(
            body.get("filename"),
            "filename is required",
        )
        filename = _normalize_top_level_md_filename(raw_filename)
        text = _require_string(body.get("text"), "text is required")

        raw_agent_id = _require_string(
            body.get("agentId"),
            "agentId is required",
        )
        agent_id = raw_agent_id.strip()
        if not agent_id:
            raise HTTPException(status_code=400, detail="agentId is required")

        workspace = await get_agent_for_request(request, agent_id=agent_id)
        workspace_manager = AgentMdManager(str(workspace.workspace_dir))
        workspace_manager.append_working_md(filename, text)
        return {
            "appended": True,
            "filename": filename,
            "agent_id": agent_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/files",
    response_model=list[MdFileInfo],
    summary="List working files",
    description="List all working files (uses active agent)",
)
async def list_working_files(
    request: Request,
) -> list[MdFileInfo]:
    """List working directory markdown files."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        files = [
            MdFileInfo.model_validate(file)
            for file in workspace_manager.list_working_mds()
        ]
        return files
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/files/{md_name}",
    response_model=MdFileContent,
    summary="Read a working file",
    description="Read a working markdown file (uses active agent)",
)
async def read_working_file(
    md_name: str,
    request: Request,
) -> MdFileContent:
    """Read a working directory markdown file."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        content = workspace_manager.read_working_md(md_name)
        return MdFileContent(content=content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put(
    "/files/{md_name}",
    response_model=dict,
    summary="Write a working file",
    description="Create or update a working file (uses active agent)",
)
async def write_working_file(
    md_name: str,
    body: MdFileContent,
    request: Request,
) -> dict:
    """Write a working directory markdown file."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        workspace_manager.write_working_md(md_name, body.content)
        return {"written": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/memory",
    response_model=list[MdFileInfo],
    summary="List memory files",
    description="List all memory files (uses active agent)",
)
async def list_memory_files(
    request: Request,
) -> list[MdFileInfo]:
    """List memory directory markdown files."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        files = [
            MdFileInfo.model_validate(file)
            for file in workspace_manager.list_memory_mds()
        ]
        return files
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/memory/{md_name}",
    response_model=MdFileContent,
    summary="Read a memory file",
    description="Read a memory markdown file (uses active agent)",
)
async def read_memory_file(
    md_name: str,
    request: Request,
) -> MdFileContent:
    """Read a memory directory markdown file."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        content = workspace_manager.read_memory_md(md_name)
        return MdFileContent(content=content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put(
    "/memory/{md_name}",
    response_model=dict,
    summary="Write a memory file",
    description="Create or update a memory file (uses active agent)",
)
async def write_memory_file(
    md_name: str,
    body: MdFileContent,
    request: Request,
) -> dict:
    """Write a memory directory markdown file."""
    try:
        workspace = await get_agent_for_request(request)
        workspace_manager = AgentMdManager(
            str(workspace.workspace_dir),
        )
        workspace_manager.write_memory_md(md_name, body.content)
        return {"written": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/language",
    summary="Get agent language",
    description="Get the language setting for agent MD files (en/zh/ru)",
)
async def get_agent_language(request: Request) -> dict:
    """Get agent language setting for current agent."""
    workspace, agent_config = await get_agent_and_config_for_request(request)
    return {
        "language": agent_config.language,
        "agent_id": workspace.agent_id,
    }


@router.put(
    "/language",
    summary="Update agent language",
    description=(
        "Update the language for agent MD files (en/zh/ru). "
        "Optionally copies MD files for the new language to agent workspace."
    ),
)
async def put_agent_language(
    request: Request,
    body: dict = Body(
        ...,
        description='Language setting, e.g. {"language": "zh"}',
    ),
) -> dict:
    """
    Update agent language and optionally re-copy MD files to agent workspace.
    """
    language = (body.get("language") or "").strip().lower()
    valid = {"zh", "en", "ru"}
    if language not in valid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid language '{language}'. "
                f"Must be one of: {', '.join(sorted(valid))}"
            ),
        )

    # Get current agent's workspace
    workspace, agent_config = await get_agent_and_config_for_request(request)
    agent_id = workspace.agent_id
    old_language = agent_config.language

    # Update agent's language
    agent_config.language = language
    save_agent_config(agent_id, agent_config, tenant_id=workspace.tenant_id)

    copied_files: list[str] = []
    if old_language != language:
        # Builtin QA: persona from md_files/qa/; MEMORY/HEARTBEAT from lang
        # pack; never BOOTSTRAP (remove if wrongly copied earlier).
        if agent_id == BUILTIN_QA_AGENT_ID:
            copied_files = copy_builtin_qa_md_files(
                language,
                workspace.workspace_dir,
                only_if_missing=False,
            )
        else:
            copied_files = (
                copy_md_files(
                    language,
                    workspace_dir=workspace.workspace_dir,
                )
                or []
            )

    return {
        "language": language,
        "copied_files": copied_files,
        "agent_id": agent_id,
    }


@router.get(
    "/audio-mode",
    summary="Get audio mode",
    description=(
        "Get the audio handling mode for incoming voice messages. "
        'Values: "auto", "native".'
    ),
)
async def get_audio_mode() -> dict:
    """Get audio mode setting."""
    config = load_config()
    return {"audio_mode": config.agents.audio_mode}


@router.put(
    "/audio-mode",
    summary="Update audio mode",
    description=(
        "Update how incoming audio/voice messages are handled. "
        '"auto": transcribe if provider available, else file placeholder; '
        '"native": send audio directly to model (may need ffmpeg).'
    ),
)
async def put_audio_mode(
    body: dict = Body(
        ...,
        description='Audio mode, e.g. {"audio_mode": "auto"}',
    ),
) -> dict:
    """Update audio mode setting."""
    raw = body.get("audio_mode")
    audio_mode = (str(raw) if raw is not None else "").strip().lower()
    valid = {"auto", "native"}
    if audio_mode not in valid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid audio_mode '{audio_mode}'. "
                f"Must be one of: {', '.join(sorted(valid))}"
            ),
        )
    config = load_config()
    config.agents.audio_mode = audio_mode
    save_config(config)
    return {"audio_mode": audio_mode}


@router.get(
    "/transcription-provider-type",
    summary="Get transcription provider type",
    description=(
        "Get the transcription provider type. "
        'Values: "disabled", "whisper_api", "local_whisper".'
    ),
)
async def get_transcription_provider_type() -> dict:
    """Get transcription provider type setting."""
    config = load_config()
    return {
        "transcription_provider_type": (
            config.agents.transcription_provider_type
        ),
    }


@router.put(
    "/transcription-provider-type",
    summary="Set transcription provider type",
    description=(
        "Set the transcription provider type. "
        '"disabled": no transcription; '
        '"whisper_api": remote Whisper endpoint; '
        '"local_whisper": locally installed openai-whisper.'
    ),
)
async def put_transcription_provider_type(
    body: dict = Body(
        ...,
        description=(
            "Provider type, e.g. "
            '{"transcription_provider_type": "whisper_api"}'
        ),
    ),
) -> dict:
    """Set the transcription provider type."""
    raw = body.get("transcription_provider_type")
    provider_type = (str(raw) if raw is not None else "").strip().lower()
    valid = {"disabled", "whisper_api", "local_whisper"}
    if provider_type not in valid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid transcription_provider_type '{provider_type}'. "
                f"Must be one of: {', '.join(sorted(valid))}"
            ),
        )
    config = load_config()
    config.agents.transcription_provider_type = provider_type
    save_config(config)
    return {"transcription_provider_type": provider_type}


@router.get(
    "/local-whisper-status",
    summary="Check local whisper availability",
    description=(
        "Check whether the local whisper provider can be used. "
        "Returns availability of ffmpeg and openai-whisper."
    ),
)
async def get_local_whisper_status() -> dict:
    """Check local whisper dependencies."""
    from ...agents.utils.audio_transcription import (
        check_local_whisper_available,
    )

    return check_local_whisper_available()


@router.get(
    "/transcription-providers",
    summary="List transcription providers",
    description=(
        "List providers capable of audio transcription (Whisper API). "
        "Returns available providers and the configured selection."
    ),
)
async def get_transcription_providers() -> dict:
    """List transcription-capable providers and configured selection."""
    from ...agents.utils.audio_transcription import (
        get_configured_transcription_provider_id,
        list_transcription_providers,
    )

    return {
        "providers": list_transcription_providers(),
        "configured_provider_id": (get_configured_transcription_provider_id()),
    }


@router.put(
    "/transcription-provider",
    summary="Set transcription provider",
    description=(
        "Set the provider to use for audio transcription. "
        'Use empty string "" to unset.'
    ),
)
async def put_transcription_provider(
    body: dict = Body(
        ...,
        description=(
            'Provider ID, e.g. {"provider_id": "openai"} '
            'or {"provider_id": ""} to unset'
        ),
    ),
) -> dict:
    """Set the transcription provider."""
    provider_id = (body.get("provider_id") or "").strip()
    config = load_config()
    config.agents.transcription_provider_id = provider_id
    save_config(config)
    return {"provider_id": provider_id}


@router.get(
    "/running-config",
    response_model=AgentsRunningConfig,
    summary="Get agent running config",
    description="Get running configuration for active agent",
)
async def get_agents_running_config(
    request: Request,
) -> AgentsRunningConfig:
    """Get agent running configuration."""
    _, agent_config = await get_agent_and_config_for_request(request)
    return agent_config.running or AgentsRunningConfig()


@router.put(
    "/running-config",
    response_model=AgentsRunningConfig,
    summary="Update agent running config",
    description="Update running configuration for active agent",
)
async def put_agents_running_config(
    running_config: AgentsRunningConfig = Body(
        ...,
        description="Updated agent running configuration",
    ),
    request: Request = None,
) -> AgentsRunningConfig:
    """Update agent running configuration."""
    workspace, agent_config = await get_agent_and_config_for_request(request)
    agent_config.running = running_config
    save_agent_config(
        workspace.agent_id,
        agent_config,
        tenant_id=workspace.tenant_id,
    )

    # Hot reload config (async, non-blocking)
    schedule_agent_reload(
        request,
        workspace.agent_id,
        tenant_id=workspace.tenant_id,
    )

    return running_config


@router.get(
    "/system-prompt-files",
    response_model=list[str],
    summary="Get system prompt files",
    description="Get system prompt files for active agent",
)
async def get_system_prompt_files(
    request: Request,
) -> list[str]:
    """Get list of enabled system prompt files."""
    _, agent_config = await get_agent_and_config_for_request(request)
    return agent_config.system_prompt_files or []


@router.put(
    "/system-prompt-files",
    response_model=list[str],
    summary="Update system prompt files",
    description="Update system prompt files for active agent",
)
async def put_system_prompt_files(
    files: list[str] = Body(
        ...,
        description="Markdown filenames to load into system prompt",
    ),
    request: Request = None,
) -> list[str]:
    """Update list of enabled system prompt files."""
    workspace, agent_config = await get_agent_and_config_for_request(request)
    agent_config.system_prompt_files = files
    save_agent_config(
        workspace.agent_id,
        agent_config,
        tenant_id=workspace.tenant_id,
    )

    # Hot reload config (async, non-blocking)
    schedule_agent_reload(
        request,
        workspace.agent_id,
        tenant_id=workspace.tenant_id,
    )

    return files
