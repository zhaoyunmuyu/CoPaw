# -*- coding: utf-8 -*-
# flake8: noqa: E501
"""CLI init: interactively create working_dir config.json and HEARTBEAT.md."""
from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel

from .channels_cmd import configure_channels_interactive
from .env_cmd import configure_env_interactive
from .providers_cmd import configure_providers_interactive
from .skills_cmd import configure_skills_interactive
from .utils import prompt_confirm, prompt_choice
from ..config import (
    get_config_path,
    get_heartbeat_query_path,
    load_config,
    save_config,
)
from ..config.config import (
    ActiveHoursConfig,
    Config,
    HeartbeatConfig,
)
from ..constant import HEARTBEAT_DEFAULT_EVERY
from ..providers import load_providers_json

SECURITY_WARNING = """
Security warning — please read.

CoPaw is a personal assistant that runs in your own environment. It can connect to
channels (DingTalk, Feishu, QQ, Discord, iMessage, etc.) and run skills that read
files, run commands, and call external APIs. By default it is a single-operator
boundary: one trusted user. A malicious or confused prompt can lead the agent to
do unsafe things if tools are enabled.

If multiple people can message the same CoPaw instance with tools enabled, they
share the same delegated authority (files, commands, secrets the agent can use).

If you are not comfortable with access control and hardening, do not run CoPaw with
tools or expose it to untrusted users. Get help from someone experienced before
enabling powerful skills or exposing the bot to the internet.

Recommended baseline:
- Restrict which channels and users can trigger the agent; use allowlists where possible.
- Multi-user or shared inbox: use separate config/credentials and ideally separate
  OS users or hosts per trust boundary.
- Run skills with least privilege; sandbox where you can.
- Keep secrets out of the agent's working directory and skill-accessible paths.
- Use a capable model when the agent has tools or handles untrusted input.

Review your config and skills regularly; limit tool scope to what you need.
"""


def _echo_security_warning_box() -> None:
    """Print SECURITY_WARNING in a rich panel with blue border."""
    console = Console()
    console.print(
        Panel(
            SECURITY_WARNING.strip(),
            title="[bold]🐾 Security warning — please read[/bold]",
            border_style="blue",
        ),
    )


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


def _handle_security_acceptance(
    use_defaults: bool,
    accept_security: bool,
) -> None:
    """Handle security warning acceptance. Aborts if user declines."""
    _echo_security_warning_box()
    if use_defaults and accept_security:
        click.echo(
            "Security acceptance assumed (--accept-security with --defaults).",
        )
        return

    accepted = prompt_confirm(
        "Have you read and accepted the security notice above? (yes to continue, no to abort)",
        default=True,
    )
    if not accepted:
        click.echo(
            "Initialization aborted. Read the security notice and run again when ready.",
        )
        raise click.Abort()


def _copy_from_default_user(
    user_id: str,
    working_dir,
    default_working_dir,
    default_secret_dir,
) -> bool:
    """Copy configuration from default user to new user.

    Returns:
        True if initialization is complete, False if should continue with templates.
    """
    from ..agents.utils.setup_utils import (
        _copy_default_config_files,
        _copy_default_working_files,
    )
    from ..constant import DEFAULT_SECRET_DIR

    if not (default_working_dir.exists() or default_secret_dir.exists()):
        return False

    click.echo("\n=== Copying from default user ===")
    copied_working = []
    copied_secret = []

    if default_working_dir.exists():
        copied_working = _copy_default_working_files(
            default_working_dir, working_dir
        )
        if copied_working:
            click.echo(
                f"✓ Copied from default working dir: {', '.join(copied_working)}"
            )

    if default_secret_dir.exists():
        copied_secret = _copy_default_config_files(
            default_secret_dir,
            DEFAULT_SECRET_DIR / user_id,
        )
        if copied_secret:
            click.echo(
                f"✓ Copied from default secret dir: {', '.join(copied_secret)}"
            )

    if copied_working or copied_secret:
        return True

    click.echo("No files copied from default user, using templates...")
    return False


def _configure_heartbeat_interactive(use_defaults: bool) -> HeartbeatConfig:
    """Configure heartbeat settings interactively or with defaults."""
    if use_defaults:
        return HeartbeatConfig(
            every=HEARTBEAT_DEFAULT_EVERY,
            target="main",
            active_hours=None,
        )

    click.echo("\n=== Heartbeat Configuration ===")
    every = click.prompt(
        "Heartbeat interval (e.g. 30m, 1h)",
        default=HEARTBEAT_DEFAULT_EVERY,
        type=str,
    ).strip()

    target = prompt_choice(
        "Heartbeat target:",
        options=["main", "last"],
        default="main",
    ).lower()

    active_hours = None
    use_active = prompt_confirm(
        "Set active hours for heartbeat? (skip = run 24h)",
        default=False,
    )
    if use_active:
        start = click.prompt("Active start (HH:MM)", default="08:00", type=str)
        end = click.prompt("Active end (HH:MM)", default="22:00", type=str)
        active_hours = ActiveHoursConfig(start=start.strip(), end=end.strip())

    return HeartbeatConfig(
        every=every or HEARTBEAT_DEFAULT_EVERY,
        target=target or "main",
        active_hours=active_hours,
    )


def _configure_main_config(
    config_path,
    use_defaults: bool,
    force: bool,
) -> bool:
    """Configure main config.json file.

    Returns:
        True if config was written, False if skipped.
    """
    write_config = True
    if config_path.is_file() and not force and not use_defaults:
        prompt_text = (
            f"{config_path} exists. Do you want to overwrite it? "
            '("no" for skipping the configuration process)'
        )
        write_config = prompt_confirm(prompt_text, default=False)

    if not write_config:
        click.echo("Skipping configuration.")
        return False

    hb = _configure_heartbeat_interactive(use_defaults)
    existing = (
        load_config(config_path) if config_path.is_file() else Config()
    )
    existing.agents.defaults.heartbeat = hb

    # show_tool_details
    if use_defaults:
        existing.show_tool_details = True
    else:
        existing.show_tool_details = prompt_confirm(
            "Show tool call/result details in channel messages?",
            default=True,
        )

    # language selection
    if not use_defaults:
        language = prompt_choice(
            "Select language for MD files:",
            options=["zh", "en", "ru"],
            default=existing.agents.language,
        )
        existing.agents.language = language

    # channels
    if not use_defaults and prompt_confirm(
        "Configure channels? "
        "(iMessage/Discord/DingTalk/Feishu/QQ/Console)",
        default=False,
    ):
        configure_channels_interactive(existing)

    save_config(existing, config_path)
    click.echo(f"\n✓ Configuration saved to {config_path}")
    return True


def _configure_llm(use_defaults: bool) -> None:
    """Configure LLM provider settings."""
    data = load_providers_json()
    has_llm = bool(data.active_llm.provider_id and data.active_llm.model)

    if has_llm:
        click.echo(
            f"\n✓ LLM already configured: "
            f"{data.active_llm.provider_id} / {data.active_llm.model}",
        )
        if not use_defaults and prompt_confirm(
            "Reconfigure LLM provider?",
            default=False,
        ):
            click.echo("\n=== LLM Provider Configuration ===")
            configure_providers_interactive(use_defaults=False)
        else:
            click.echo("Skipped LLM configuration.")
    else:
        click.echo("\n=== LLM Provider Configuration (required) ===")
        configure_providers_interactive(use_defaults=use_defaults)


def _configure_skills(use_defaults: bool, write_config: bool) -> None:
    """Configure skills settings."""
    from ..agents.skills_manager import sync_skills_to_working_dir

    if use_defaults:
        click.echo("Enabling all skills by default (skip existing)...")
        synced, skipped = sync_skills_to_working_dir(
            skill_names=None,
            force=False,
        )
        if skipped:
            click.echo(
                f"✓ Skills synced: {synced}, skipped (existing): {skipped}",
            )
        else:
            click.echo(f"✓ All {synced} skills enabled.")
        return

    if not write_config:
        return

    skills_choice = prompt_choice(
        "Configure skills:",
        options=["all", "none", "custom"],
        default="all",
    )

    if skills_choice == "all":
        click.echo("Enabling all skills...")
        synced, skipped = sync_skills_to_working_dir(
            skill_names=None,
            force=False,
        )
        click.echo(f"✓ Skills synced: {synced}, skipped: {skipped}")
    elif skills_choice == "custom":
        configure_skills_interactive()
    else:
        click.echo("Skipped skills configuration.")


def _configure_md_files(
    config_path,
    use_defaults: bool,
    force: bool,
) -> None:
    """Configure and copy MD files."""
    from ..agents.utils import copy_md_files

    config = load_config(config_path) if config_path.is_file() else Config()
    current_language = config.agents.language
    installed_language = config.agents.installed_md_files_language

    if use_defaults:
        click.echo(f"\nChecking MD files [language: {current_language}]...")
        copied = copy_md_files(current_language, skip_existing=True)
        if copied:
            config.agents.installed_md_files_language = current_language
            save_config(config, config_path)
            click.echo(
                f"✓ Copied {len(copied)} md file(s): " + ", ".join(copied),
            )
        else:
            click.echo("✓ MD files already present, skipped.")
        return

    if installed_language != current_language or force:
        click.echo(f"\nChecking MD files [language: {current_language}]...")
        if installed_language and installed_language != current_language:
            click.echo(
                f"Language changed: {installed_language} → {current_language}",
            )
        copied = copy_md_files(current_language)
        if copied:
            config.agents.installed_md_files_language = current_language
            save_config(config, config_path)
            click.echo(
                f"✓ Copied {len(copied)} md file(s): " + ", ".join(copied),
            )
        else:
            click.echo("⚠ No md files copied")
    else:
        click.echo(
            f"\n✓ MD files [{current_language}] are already up to date.",
        )


def _configure_heartbeat_md(
    heartbeat_path,
    config_path,
    use_defaults: bool,
    force: bool,
) -> None:
    """Configure HEARTBEAT.md file."""
    config = load_config(config_path) if config_path.is_file() else Config()
    current_language = config.agents.language

    write_heartbeat = True
    if heartbeat_path.is_file() and not force:
        if use_defaults:
            click.echo("✓ HEARTBEAT.md already present, skipped.")
            write_heartbeat = False
        else:
            write_heartbeat = prompt_confirm(
                f"{heartbeat_path} exists. Overwrite?",
                default=False,
            )

    if not write_heartbeat:
        if not use_defaults:
            click.echo("Skipped HEARTBEAT.md.")
        return

    default_content = DEFAULT_HEARTBEAT_MDS[current_language]
    if use_defaults:
        content = default_content
    else:
        click.echo("\n=== Heartbeat Query Configuration ===")
        if prompt_confirm(
            "Edit heartbeat query in your default editor?",
            default=True,
        ):
            content = click.edit(
                default_content,
                extension=".md",
                require_save=False,
            )
            if content is None:
                content = default_content
        else:
            content = default_content

    heartbeat_path.write_text(
        content.strip() or default_content,
        encoding="utf-8",
    )
    click.echo(f"✓ Heartbeat query saved to {heartbeat_path}")


@click.command("init")
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing config.json and HEARTBEAT.md if present.",
)
@click.option(
    "--defaults",
    "use_defaults",
    is_flag=True,
    help="Use defaults only, no interactive prompts (for scripts).",
)
@click.option(
    "--accept-security",
    "accept_security",
    is_flag=True,
    help="Skip security confirmation (use with --defaults for scripts/Docker).",
)
@click.option(
    "--user-id",
    default=None,
    help="User-specific subdirectory for multi-user isolation.",
)
def init_cmd(
    force: bool,
    use_defaults: bool,
    accept_security: bool,
    user_id: str | None,
) -> None:
    """Create working dir with config.json and HEARTBEAT.md (interactive)."""
    from ..constant import (
        set_current_user,
        DEFAULT_WORKING_DIR,
        DEFAULT_SECRET_DIR,
    )

    # Auto-enable non-interactive mode when --user-id is specified
    if user_id and not use_defaults:
        use_defaults = True
        accept_security = True
        click.echo(f"User ID: {user_id} (auto non-interactive mode)")

    set_current_user(user_id)

    if user_id:
        click.echo(f"User ID: {user_id}")
    config_path = get_config_path(user_id)
    working_dir = config_path.parent
    heartbeat_path = get_heartbeat_query_path(user_id)

    click.echo(f"Working dir: {working_dir}")

    # Security warning
    _handle_security_acceptance(use_defaults, accept_security)
    working_dir.mkdir(parents=True, exist_ok=True)

    # Copy from default user for non-default users
    if user_id and user_id != "default":
        default_working_dir = DEFAULT_WORKING_DIR / "default"
        default_secret_dir = DEFAULT_SECRET_DIR / "default"
        if _copy_from_default_user(
            user_id, working_dir, default_working_dir, default_secret_dir
        ):
            click.echo("\n✓ Initialization complete!")
            return

    # Copy init config files (config.json and providers.json)
    from ..agents.utils.setup_utils import copy_init_config_files

    click.echo("\n=== Initial Configuration Files ===")
    config_copied, providers_copied = copy_init_config_files(
        user_id=user_id,
        force=force,
        skip_existing=use_defaults and not force,
    )
    click.echo(
        "✓ Copied config.json template (channels, MCP settings)"
        if config_copied
        else "✓ config.json already exists or not copied"
    )
    click.echo(
        "✓ Copied providers.json template (model provider settings)"
        if providers_copied
        else "✓ providers.json already exists or not copied"
    )

    # Configure main config.json
    write_config = _configure_main_config(config_path, use_defaults, force)

    # Configure LLM
    _configure_llm(use_defaults)

    # Configure skills
    _configure_skills(use_defaults, write_config)

    # Configure environment variables
    if not use_defaults:
        if prompt_confirm("Configure environment variables?", default=False):
            configure_env_interactive()
        else:
            click.echo("Skipped environment variable configuration.")

    # Configure MD files
    _configure_md_files(config_path, use_defaults, force)

    # Configure HEARTBEAT.md
    _configure_heartbeat_md(heartbeat_path, config_path, use_defaults, force)

    click.echo("\n✓ Initialization complete!")
