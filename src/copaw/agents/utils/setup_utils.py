# -*- coding: utf-8 -*-
"""Setup and initialization utilities for agent configuration.

This module handles copying markdown configuration files to
the working directory.
"""
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Default HEARTBEAT.md content for different languages
DEFAULT_HEARTBEAT_MDS = {
    "zh": """# Heartbeat checklist
- 扫描收件箱紧急邮件
- 查看未来 2h 的日历
- 检查待办是否卡住
- 若安静超过 8h，轻量 check-in
""",
    "en": """# Heartbeat checklist
- Scan inbox for urgent email
- Check calendar for next 2h
- Check tasks for blockers
- Light check-in if quiet for 8h
""",
    "ru": """# Heartbeat checklist
- Проверить входящие на срочные письма
- Просмотреть календарь на ближайшие 2 часа
- Проверить задачи на наличие блокировок
- Лёгкая проверка при отсутствии активности более 8 часов
""",
}


def initialize_user_directory(
    user_id: str,
    language: str = "en",
) -> bool:
    """Initialize user directory with minimal required files.

    This function is called automatically when a request is received
    from a new user. It creates the minimum set of files and directories
    required for the agent to function.

    Args:
        user_id: User identifier
        language: Language code for default config (default: "en")

    Returns:
        True if initialization was performed, False if directory already existed
    """
    from ...constant import get_working_dir, get_secret_dir
    from ...config import Config, save_config, get_heartbeat_query_path
    from ...providers.store import ensure_providers_json
    from ...agents.skills_manager import sync_skills_to_working_dir

    working_dir = get_working_dir(user_id)
    secret_dir = get_secret_dir(user_id)

    # Check if already initialized (config.json exists)
    config_path = working_dir / "config.json"
    if config_path.exists():
        logger.debug("User %s directory already initialized", user_id)
        return False

    # Create base directories
    working_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.mkdir(parents=True, exist_ok=True)

    # Create default config.json
    config = Config()
    config.agents.language = language
    save_config(config, config_path)
    logger.info("Created default config.json for user %s", user_id)

    # Create default providers.json (without API keys)
    ensure_providers_json(user_id)
    logger.info("Created default providers.json for user %s", user_id)

    # Sync built-in skills to active_skills (required for agent to work)
    sync_skills_to_working_dir(force=False)
    logger.info("Synced built-in skills for user %s", user_id)

    # Copy MD files (AGENTS.md, BOOTSTRAP.md, SOUL.md, PROFILE.md, MEMORY.md)
    # Pass the user-specific working directory explicitly
    # Note: HEARTBEAT.md is handled separately below with default content
    copied_files = copy_md_files(language, skip_existing=True, target_dir=working_dir, exclude_files=["HEARTBEAT.md"])
    if copied_files:
        logger.info(
            "Copied %d md file(s) for user %s: %s",
            len(copied_files),
            user_id,
            ", ".join(copied_files),
        )
    else:
        logger.warning("No md files copied for user %s", user_id)

    # Create default HEARTBEAT.md if not exists
    heartbeat_path = get_heartbeat_query_path(user_id)
    if not heartbeat_path.exists():
        heartbeat_content = DEFAULT_HEARTBEAT_MDS.get(
            language,
            DEFAULT_HEARTBEAT_MDS["en"],
        )
        heartbeat_path.write_text(heartbeat_content.strip(), encoding="utf-8")
        logger.info("Created default HEARTBEAT.md for user %s", user_id)

    logger.info(
        "User %s directory initialized at %s",
        user_id,
        working_dir,
    )
    return True


def copy_md_files(
    language: str,
    skip_existing: bool = False,
    target_dir: Path | None = None,
    exclude_files: list[str] | None = None,
) -> list[str]:
    """Copy md files from agents/md_files to working directory.

    Args:
        language: Language code (e.g. 'en', 'zh')
        skip_existing: If True, skip files that already exist in working dir.
        target_dir: Optional target directory. If None, uses request-scoped
                    working directory.
        exclude_files: Optional list of filenames to exclude from copying.

    Returns:
        List of copied file names.
    """
    # Get md_files directory path with language subdirectory
    md_files_dir = Path(__file__).parent.parent / "md_files" / language

    if not md_files_dir.exists():
        logger.warning(
            "MD files directory not found: %s, falling back to 'en'",
            md_files_dir,
        )
        # Fallback to English if specified language not found
        md_files_dir = Path(__file__).parent.parent / "md_files" / "en"
        if not md_files_dir.exists():
            logger.error("Default 'en' md files not found either")
            return []

    # Use provided target_dir or fall back to request-scoped working dir
    if target_dir is not None:
        working_dir = target_dir
    else:
        from ...constant import get_request_working_dir
        working_dir = get_request_working_dir()

    working_dir.mkdir(parents=True, exist_ok=True)

    # Build exclude set for quick lookup
    exclude_set = set(exclude_files) if exclude_files else set()

    # Copy all .md files to working directory
    copied_files: list[str] = []
    for md_file in md_files_dir.glob("*.md"):
        # Skip excluded files
        if md_file.name in exclude_set:
            logger.debug("Excluded md file: %s", md_file.name)
            continue

        target_file = working_dir / md_file.name
        if skip_existing and target_file.exists():
            logger.debug("Skipped existing md file: %s", md_file.name)
            continue
        try:
            shutil.copy2(md_file, target_file)
            logger.debug("Copied md file: %s", md_file.name)
            copied_files.append(md_file.name)
        except Exception as e:
            logger.error(
                "Failed to copy md file '%s': %s",
                md_file.name,
                e,
            )

    if copied_files:
        logger.debug(
            "Copied %d md file(s) [%s] to %s",
            len(copied_files),
            language,
            working_dir,
        )

    return copied_files
