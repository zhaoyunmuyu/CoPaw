# -*- coding: utf-8 -*-
"""Setup and initialization utilities for agent configuration.

This module handles copying markdown configuration files to
the working directory.
"""
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def _copy_default_config_files(
    src_dir: Path,
    dst_dir: Path,
) -> list[str]:
    """Copy configuration files from default user's directory to new user's directory.

    This function copies providers.json and config.json from the default user's
    directories to initialize a new user with the same configuration.

    Args:
        src_dir: Source secret directory (default user's secret dir)
        dst_dir: Destination secret directory (new user's secret dir)

    Returns:
        List of copied file names.
    """
    copied_files: list[str] = []

    # Ensure destination directory exists
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Copy providers.json from secret directory
    src_providers = src_dir / "providers.json"
    dst_providers = dst_dir / "providers.json"
    if src_providers.exists() and not dst_providers.exists():
        try:
            shutil.copy2(src_providers, dst_providers)
            copied_files.append("providers.json")
            logger.debug("Copied providers.json from default user")
        except Exception as e:
            logger.error("Failed to copy providers.json: %s", e)

    return copied_files


def _copy_default_working_files(
    src_working_dir: Path,
    dst_working_dir: Path,
    exclude_files: list[str] | None = None,
) -> list[str]:
    """Copy working directory files from default user to new user.

    This copies config.json and md files from the default user's working directory.

    Args:
        src_working_dir: Source working directory (default user's working dir)
        dst_working_dir: Destination working directory (new user's working dir)
        exclude_files: Optional list of filenames to exclude from copying.

    Returns:
        List of copied file names.
    """
    copied_files: list[str] = []
    exclude_set = set(exclude_files) if exclude_files else set()

    # Copy config.json from working directory
    src_config = src_working_dir / "config.json"
    dst_config = dst_working_dir / "config.json"
    if src_config.exists() and not dst_config.exists():
        try:
            shutil.copy2(src_config, dst_config)
            copied_files.append("config.json")
            logger.debug("Copied config.json from default user")
        except Exception as e:
            logger.error("Failed to copy config.json: %s", e)

    # Copy all .md files from default user
    for md_file in src_working_dir.glob("*.md"):
        if md_file.name in exclude_set:
            continue
        dst_file = dst_working_dir / md_file.name
        if not dst_file.exists():
            try:
                shutil.copy2(md_file, dst_file)
                copied_files.append(md_file.name)
                logger.debug(
                    "Copied md file from default user: %s", md_file.name
                )
            except Exception as e:
                logger.error(
                    "Failed to copy md file '%s': %s", md_file.name, e
                )

    return copied_files


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

    Initialization logic:
    1. For "default" user:
       - Copy config.json, providers.json from md_files templates
       - Copy md files (AGENTS.md, BOOTSTRAP.md, etc.) from md_files templates
    2. For other users:
       - Copy config.json, providers.json, md files from default user if exists
       - Fallback to md_files templates if default user doesn't exist

    Args:
        user_id: User identifier
        language: Language code for default config (default: "en")

    Returns:
        True if initialization was performed, False if directory already existed
    """
    from ...constant import (
        get_working_dir,
        get_secret_dir,
        DEFAULT_WORKING_DIR,
        DEFAULT_SECRET_DIR,
    )
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

    # Determine source of configuration
    md_copied = False  # Track if md files were copied
    if user_id == "default":
        # For default user: copy from md_files templates
        config_copied, providers_copied = copy_init_config_files(
            user_id=user_id,
            skip_existing=True,
        )
        if config_copied:
            logger.info("Copied config.json from templates for default user")
        if providers_copied:
            logger.info(
                "Copied providers.json from templates for default user"
            )

        # Copy MD files from templates for default user
        copied_md = copy_md_files(
            language,
            skip_existing=True,
            target_dir=working_dir,
            exclude_files=["HEARTBEAT.md"],
        )
        if copied_md:
            md_copied = True
            logger.info(
                "Copied %d md file(s) from templates for default user: %s",
                len(copied_md),
                ", ".join(copied_md),
            )
    else:
        # For other users: try to copy from default user first
        default_working_dir = DEFAULT_WORKING_DIR / "default"
        default_secret_dir = DEFAULT_SECRET_DIR / "default"

        config_copied = False
        providers_copied = False

        # Try to copy from default user's working directory (config.json + md files)
        if default_working_dir.exists():
            copied_working = _copy_default_working_files(
                default_working_dir, working_dir
            )
            if "config.json" in copied_working:
                config_copied = True
                logger.info(
                    "Copied config.json from default user for user %s", user_id
                )

            # Check if md files were copied
            md_files_copied = [f for f in copied_working if f.endswith(".md")]
            if md_files_copied:
                md_copied = True
                logger.info(
                    "Copied %d md file(s) from default user for user %s: %s",
                    len(md_files_copied),
                    user_id,
                    ", ".join(md_files_copied),
                )

        # Try to copy from default user's secret directory (providers.json)
        if default_secret_dir.exists():
            copied_secret = _copy_default_config_files(
                default_secret_dir, secret_dir
            )
            if "providers.json" in copied_secret:
                providers_copied = True
                logger.info(
                    "Copied providers.json from default user for user %s",
                    user_id,
                )

        # Fallback to templates if default user doesn't exist or copy failed
        if not config_copied or not providers_copied:
            template_config, template_providers = copy_init_config_files(
                user_id=user_id,
                skip_existing=True,
            )
            if not config_copied and template_config:
                config_copied = True
                logger.info(
                    "Copied config.json from templates for user %s", user_id
                )
            if not providers_copied and template_providers:
                providers_copied = True
                logger.info(
                    "Copied providers.json from templates for user %s", user_id
                )

        # Fallback to templates for md files if not copied from default user
        if not md_copied:
            copied_md = copy_md_files(
                language,
                skip_existing=True,
                target_dir=working_dir,
                exclude_files=["HEARTBEAT.md"],
            )
            if copied_md:
                md_copied = True
                logger.info(
                    "Copied %d md file(s) from templates for user %s: %s",
                    len(copied_md),
                    user_id,
                    ", ".join(copied_md),
                )

    # Create default config.json if still not exists
    if not config_path.exists():
        config = Config()
        config.agents.language = language
        save_config(config, config_path)
        logger.info("Created default config.json for user %s", user_id)

    # Create default providers.json if still not exists
    providers_path = secret_dir / "providers.json"
    if not providers_path.exists():
        ensure_providers_json(user_id)
        logger.info("Created default providers.json for user %s", user_id)

    # Sync built-in skills to active_skills (required for agent to work)
    sync_skills_to_working_dir(force=False)
    logger.info("Synced built-in skills for user %s", user_id)

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


def copy_init_config_files(
    user_id: str | None = None,
    force: bool = False,
    skip_existing: bool = False,
) -> tuple[bool, bool]:
    """Copy config.json and providers.json from md_files to user directories.

    This function copies the template configuration files to initialize
    model, MCP, and channel settings for a user.

    Args:
        user_id: User identifier for subdirectory isolation.
                  None uses the current runtime user directory.
        force: If True, overwrite existing files.
        skip_existing: If True, skip files that already exist (takes precedence
                       over force when both are True).

    Returns:
        Tuple of (config_copied, providers_copied) indicating which files were copied.
    """
    import os

    from ...constant import get_working_dir, get_secret_dir

    # Get md_files directory (root level, not language subdirectory)
    md_files_dir = Path(__file__).parent.parent / "md_files"

    # Determine target directories
    if user_id is not None:
        working_dir = get_working_dir(user_id)
        secret_dir = get_secret_dir(user_id)
    else:
        from ...constant import get_request_working_dir, get_request_secret_dir

        working_dir = get_request_working_dir()
        secret_dir = get_request_secret_dir()

    # Create directories if needed
    working_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.mkdir(parents=True, exist_ok=True)

    # Set secure permissions on secret directory
    try:
        os.chmod(secret_dir, 0o700)
    except OSError:
        pass

    config_copied = False
    providers_copied = False

    # Copy config.json to working directory
    src_config = md_files_dir / "config.json"
    dst_config = working_dir / "config.json"
    if src_config.exists():
        if skip_existing and dst_config.exists():
            logger.debug("Skipped existing config.json")
        elif force or not dst_config.exists():
            try:
                shutil.copy2(src_config, dst_config)
                config_copied = True
                logger.info("Copied config.json to %s", dst_config)
            except Exception as e:
                logger.error("Failed to copy config.json: %s", e)
    else:
        logger.warning("Source config.json not found: %s", src_config)

    # Copy providers.json to secret directory
    src_providers = md_files_dir / "providers.json"
    dst_providers = secret_dir / "providers.json"
    if src_providers.exists():
        if skip_existing and dst_providers.exists():
            logger.debug("Skipped existing providers.json")
        elif force or not dst_providers.exists():
            try:
                shutil.copy2(src_providers, dst_providers)
                # Set secure permissions on providers.json
                try:
                    os.chmod(dst_providers, 0o600)
                except OSError:
                    pass
                providers_copied = True
                logger.info("Copied providers.json to %s", dst_providers)
            except Exception as e:
                logger.error("Failed to copy providers.json: %s", e)
    else:
        logger.warning("Source providers.json not found: %s", src_providers)

    return config_copied, providers_copied
