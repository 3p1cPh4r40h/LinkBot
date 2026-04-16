import asyncio
import json
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Any, Final
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


DELETE_DELAY_SECONDS: Final[float] = 0.4
DEFAULT_LINK_MESSAGE: Final[str] = "New Link"
SETTINGS_FILE: Final[str] = "guild_settings.json"
LOG_FILE: Final[str] = "linkbot.log"
LOG_MAX_BYTES: Final[int] = 1_000_000
LOG_BACKUP_COUNT: Final[int] = 3
URL_PATTERN: Final[re.Pattern[str]] = re.compile(r"(?:https?://|www\.)\S+")

ACTION_CHOICES: Final[list[app_commands.Choice[str]]] = [
    app_commands.Choice(name="List", value="list"),
    app_commands.Choice(name="Add", value="add"),
    app_commands.Choice(name="Remove", value="remove"),
    app_commands.Choice(name="Clear", value="clear"),
]
ADMIN_COMMAND_KEYS: Final[list[str]] = [
    "safe-link",
    "link-message",
    "link-message-reset",
    "link-channel",
    "link-role",
    "link-status",
    "link-help",
    "link-command-role",
]
ADMIN_COMMAND_CHOICES: Final[list[app_commands.Choice[str]]] = [
    app_commands.Choice(name="/safe-link", value="safe-link"),
    app_commands.Choice(name="/link-message", value="link-message"),
    app_commands.Choice(name="/link-message-reset", value="link-message-reset"),
    app_commands.Choice(name="/link-channel", value="link-channel"),
    app_commands.Choice(name="/link-role", value="link-role"),
    app_commands.Choice(name="/link-status", value="link-status"),
    app_commands.Choice(name="/link-help", value="link-help"),
    app_commands.Choice(name="/link-command-role", value="link-command-role"),
]

logger = logging.getLogger("linkbot")


def normalize_id_list(raw_values: object) -> list[int]:
    if not isinstance(raw_values, list):
        return []

    normalized_values: set[int] = set()
    for value in raw_values:
        if isinstance(value, int):
            normalized_values.add(value)
            continue

        if isinstance(value, str) and value.isdigit():
            normalized_values.add(int(value))

    return sorted(normalized_values)


def normalize_id_map(raw_values: object) -> dict[str, int]:
    if not isinstance(raw_values, dict):
        return {}

    normalized_values: dict[str, int] = {}
    for key, value in raw_values.items():
        if isinstance(value, int):
            normalized_values[str(key)] = value
            continue

        if isinstance(value, str) and value.isdigit():
            normalized_values[str(key)] = int(value)

    return normalized_values


def normalize_settings(raw_settings: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_settings, dict):
        return {}

    normalized_settings: dict[str, dict[str, Any]] = {}
    for guild_id, values in raw_settings.items():
        if not isinstance(values, dict):
            continue

        message_prefix = values.get("message_prefix", DEFAULT_LINK_MESSAGE)
        if not isinstance(message_prefix, str) or not message_prefix.strip():
            message_prefix = DEFAULT_LINK_MESSAGE

        normalized_settings[str(guild_id)] = {
            "message_prefix": message_prefix.strip(),
            "allowed_channel_ids": normalize_id_list(values.get("allowed_channel_ids")),
            "allowed_role_ids": normalize_id_list(values.get("allowed_role_ids")),
            "managed_channel_ids": normalize_id_list(values.get("managed_channel_ids")),
            "preserve_before_message_ids": normalize_id_map(
                values.get("preserve_before_message_ids")
            ),
            "command_role_ids": {
                command_name: normalize_id_list(role_ids)
                for command_name, role_ids in values.get("command_role_ids", {}).items()
                if isinstance(command_name, str)
            }
            if isinstance(values.get("command_role_ids"), dict)
            else {},
        }

    return normalized_settings


def load_settings() -> dict[str, dict[str, Any]]:
    if not os.path.exists(SETTINGS_FILE):
        return {}

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
            loaded_settings = json.load(settings_file)
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to load %s; using defaults.", SETTINGS_FILE)
        return {}

    return normalize_settings(loaded_settings)


guild_settings = load_settings()


def save_settings() -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as settings_file:
            json.dump(guild_settings, settings_file, indent=2, sort_keys=True)
    except OSError:
        logger.exception("Failed to save %s.", SETTINGS_FILE)


def get_guild_config(guild_id: int) -> dict[str, Any]:
    guild_key = str(guild_id)
    if guild_key not in guild_settings:
        guild_settings[guild_key] = {
            "message_prefix": DEFAULT_LINK_MESSAGE,
            "allowed_channel_ids": [],
            "allowed_role_ids": [],
            "managed_channel_ids": [],
            "preserve_before_message_ids": {},
            "command_role_ids": {},
        }
        return guild_settings[guild_key]

    guild_config = guild_settings[guild_key]
    guild_config.setdefault("message_prefix", DEFAULT_LINK_MESSAGE)
    guild_config.setdefault("allowed_channel_ids", [])
    guild_config.setdefault("allowed_role_ids", [])
    guild_config.setdefault("managed_channel_ids", [])
    guild_config.setdefault("preserve_before_message_ids", {})
    guild_config.setdefault("command_role_ids", {})
    return guild_config


def get_message_prefix(guild_id: int | None) -> str:
    if guild_id is None:
        return DEFAULT_LINK_MESSAGE

    return str(get_guild_config(guild_id)["message_prefix"])


def set_message_prefix(guild_id: int, message_prefix: str) -> None:
    get_guild_config(guild_id)["message_prefix"] = message_prefix.strip()
    save_settings()


def reset_message_prefix(guild_id: int) -> None:
    get_guild_config(guild_id)["message_prefix"] = DEFAULT_LINK_MESSAGE
    save_settings()


def get_allowed_channel_ids(guild_id: int) -> list[int]:
    return list(get_guild_config(guild_id)["allowed_channel_ids"])


def get_allowed_role_ids(guild_id: int) -> list[int]:
    return list(get_guild_config(guild_id)["allowed_role_ids"])


def get_managed_channel_ids(guild_id: int) -> list[int]:
    return list(get_guild_config(guild_id)["managed_channel_ids"])


def get_preserve_before_message_id(guild_id: int, channel_id: int) -> int | None:
    raw_value = get_guild_config(guild_id)["preserve_before_message_ids"].get(str(channel_id))
    if isinstance(raw_value, int):
        return raw_value

    return None


def get_command_role_ids(guild_id: int, command_name: str) -> list[int]:
    command_role_ids = get_guild_config(guild_id)["command_role_ids"]
    raw_role_ids = command_role_ids.get(command_name, [])
    return normalize_id_list(raw_role_ids)


def get_all_command_role_ids(guild_id: int) -> dict[str, list[int]]:
    raw_command_role_ids = get_guild_config(guild_id)["command_role_ids"]
    return {
        command_name: normalize_id_list(role_ids)
        for command_name, role_ids in raw_command_role_ids.items()
        if isinstance(command_name, str)
    }


def add_command_role(guild_id: int, command_name: str, role_id: int) -> bool:
    command_role_ids = get_all_command_role_ids(guild_id)
    current_role_ids = set(command_role_ids.get(command_name, []))
    if role_id in current_role_ids:
        return False

    current_role_ids.add(role_id)
    command_role_ids[command_name] = sorted(current_role_ids)
    get_guild_config(guild_id)["command_role_ids"] = command_role_ids
    save_settings()
    return True


def remove_command_role(guild_id: int, command_name: str, role_id: int) -> bool:
    command_role_ids = get_all_command_role_ids(guild_id)
    current_role_ids = set(command_role_ids.get(command_name, []))
    if role_id not in current_role_ids:
        return False

    current_role_ids.remove(role_id)
    if current_role_ids:
        command_role_ids[command_name] = sorted(current_role_ids)
    else:
        command_role_ids.pop(command_name, None)
    get_guild_config(guild_id)["command_role_ids"] = command_role_ids
    save_settings()
    return True


def clear_command_roles(guild_id: int, command_name: str) -> None:
    command_role_ids = get_all_command_role_ids(guild_id)
    command_role_ids.pop(command_name, None)
    get_guild_config(guild_id)["command_role_ids"] = command_role_ids
    save_settings()


def add_allowed_channel(guild_id: int, channel_id: int) -> bool:
    allowed_channel_ids = set(get_allowed_channel_ids(guild_id))
    if channel_id in allowed_channel_ids:
        return False

    allowed_channel_ids.add(channel_id)
    get_guild_config(guild_id)["allowed_channel_ids"] = sorted(allowed_channel_ids)
    save_settings()
    return True


def remove_allowed_channel(guild_id: int, channel_id: int) -> bool:
    allowed_channel_ids = set(get_allowed_channel_ids(guild_id))
    if channel_id not in allowed_channel_ids:
        return False

    allowed_channel_ids.remove(channel_id)
    get_guild_config(guild_id)["allowed_channel_ids"] = sorted(allowed_channel_ids)
    save_settings()
    return True


def clear_allowed_channels(guild_id: int) -> None:
    get_guild_config(guild_id)["allowed_channel_ids"] = []
    save_settings()


def add_allowed_role(guild_id: int, role_id: int) -> bool:
    allowed_role_ids = set(get_allowed_role_ids(guild_id))
    if role_id in allowed_role_ids:
        return False

    allowed_role_ids.add(role_id)
    get_guild_config(guild_id)["allowed_role_ids"] = sorted(allowed_role_ids)
    save_settings()
    return True


def remove_allowed_role(guild_id: int, role_id: int) -> bool:
    allowed_role_ids = set(get_allowed_role_ids(guild_id))
    if role_id not in allowed_role_ids:
        return False

    allowed_role_ids.remove(role_id)
    get_guild_config(guild_id)["allowed_role_ids"] = sorted(allowed_role_ids)
    save_settings()
    return True


def clear_allowed_roles(guild_id: int) -> None:
    get_guild_config(guild_id)["allowed_role_ids"] = []
    save_settings()


def add_managed_channel(
    guild_id: int,
    channel_id: int,
    *,
    preserve_before_message_id: int | None = None,
) -> None:
    managed_channel_ids = set(get_managed_channel_ids(guild_id))
    managed_channel_ids.add(channel_id)
    guild_config = get_guild_config(guild_id)
    guild_config["managed_channel_ids"] = sorted(managed_channel_ids)

    preserve_before_message_ids = dict(guild_config["preserve_before_message_ids"])
    if preserve_before_message_id is not None:
        preserve_before_message_ids[str(channel_id)] = preserve_before_message_id
    guild_config["preserve_before_message_ids"] = preserve_before_message_ids

    save_settings()


def normalize_url(value: str) -> str:
    normalized_value = value.strip()

    while normalized_value.endswith(tuple(".,!?")):
        normalized_value = normalized_value[:-1]

    while normalized_value.startswith("<"):
        normalized_value = normalized_value[1:]

    while normalized_value.endswith(">"):
        normalized_value = normalized_value[:-1]

    while normalized_value.endswith(")") and normalized_value.count(")") > normalized_value.count("("):
        normalized_value = normalized_value[:-1]

    if normalized_value.lower().startswith("www."):
        return f"https://{normalized_value}"

    return normalized_value


def is_valid_url(value: str) -> bool:
    parsed = urlparse(normalize_url(value))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def extract_urls_from_text(content: str) -> list[str]:
    extracted_urls: list[str] = []
    seen_urls: set[str] = set()

    for match in URL_PATTERN.findall(content):
        normalized_url = normalize_url(match)
        if normalized_url in seen_urls or not is_valid_url(normalized_url):
            continue

        extracted_urls.append(normalized_url)
        seen_urls.add(normalized_url)

    return extracted_urls


def get_managed_link_url(message: discord.Message) -> str | None:
    stripped_content = message.content.strip()
    if not stripped_content:
        return None

    if is_valid_url(stripped_content):
        return normalize_url(stripped_content)

    lines = [line.strip() for line in stripped_content.splitlines() if line.strip()]
    if len(lines) < 2 or not is_valid_url(lines[-1]):
        return None

    return normalize_url(lines[-1])


def format_link_message(message_prefix: str, url: str) -> str:
    cleaned_prefix = message_prefix.strip()
    if not cleaned_prefix:
        return url

    return f"{cleaned_prefix}\n{url}"


def is_server_manager(member: discord.abc.User | discord.Member) -> bool:
    if not isinstance(member, discord.Member):
        return False

    return (
        member.id == member.guild.owner_id
        or member.guild_permissions.administrator
        or member.guild_permissions.manage_guild
    )


def format_channel_reference(guild: discord.Guild, channel_id: int) -> str:
    channel = guild.get_channel(channel_id) or guild.get_thread(channel_id)
    if channel is None:
        return f"<#{channel_id}>"

    return channel.mention


def format_role_reference(guild: discord.Guild, role_id: int) -> str:
    role = guild.get_role(role_id)
    if role is None:
        return f"<@&{role_id}>"

    return role.mention


def format_command_reference(command_name: str) -> str:
    return f"`/{command_name}`"


def current_channel_ids(channel: discord.abc.GuildChannel | discord.Thread) -> set[int]:
    channel_ids = {channel.id}
    if isinstance(channel, discord.Thread) and channel.parent_id is not None:
        channel_ids.add(channel.parent_id)

    return channel_ids


def is_managed_link_channel(channel: discord.TextChannel | discord.Thread) -> bool:
    managed_channel_ids = set(get_managed_channel_ids(channel.guild.id))
    if channel.id not in managed_channel_ids:
        return False

    allowed_channel_ids = set(get_allowed_channel_ids(channel.guild.id))
    if not allowed_channel_ids:
        return True

    return bool(current_channel_ids(channel) & allowed_channel_ids)


def has_command_access(member: discord.Member, command_name: str) -> bool:
    if is_server_manager(member):
        return True

    allowed_role_ids = set(get_command_role_ids(member.guild.id, command_name))
    if not allowed_role_ids:
        return False

    member_role_ids = {role.id for role in member.roles}
    return bool(member_role_ids & allowed_role_ids)


def get_link_access_denial_reason(
    guild: discord.Guild,
    channel: discord.TextChannel | discord.Thread,
    member: discord.Member,
) -> str | None:
    if is_server_manager(member):
        return None

    allowed_channel_ids = set(get_allowed_channel_ids(guild.id))
    if allowed_channel_ids and not (current_channel_ids(channel) & allowed_channel_ids):
        allowed_channels = ", ".join(
            format_channel_reference(guild, channel_id)
            for channel_id in sorted(allowed_channel_ids)
        )
        return f"`/link` is only enabled in: {allowed_channels}"

    allowed_role_ids = set(get_allowed_role_ids(guild.id))
    if allowed_role_ids:
        author_role_ids = {role.id for role in member.roles}
        if not (author_role_ids & allowed_role_ids):
            allowed_roles = ", ".join(
                format_role_reference(guild, role_id)
                for role_id in sorted(allowed_role_ids)
            )
            return f"You need one of these roles to use `/link`: {allowed_roles}"

    return None


def status_lines(guild: discord.Guild) -> list[str]:
    message_prefix = get_message_prefix(guild.id)
    allowed_channel_ids = get_allowed_channel_ids(guild.id)
    allowed_role_ids = get_allowed_role_ids(guild.id)
    managed_channel_ids = get_managed_channel_ids(guild.id)
    safe_start_channel_ids = [
        channel_id
        for channel_id in managed_channel_ids
        if get_preserve_before_message_id(guild.id, channel_id) is not None
    ]

    channel_summary = "Any text channel"
    if allowed_channel_ids:
        channel_summary = ", ".join(
            format_channel_reference(guild, channel_id)
            for channel_id in allowed_channel_ids
        )

    role_summary = "Any member"
    if allowed_role_ids:
        role_summary = ", ".join(
            format_role_reference(guild, role_id)
            for role_id in allowed_role_ids
        )

    managed_summary = "None yet"
    if managed_channel_ids:
        managed_summary = ", ".join(
            format_channel_reference(guild, channel_id)
            for channel_id in managed_channel_ids
        )

    safe_start_summary = "None"
    if safe_start_channel_ids:
        safe_start_summary = ", ".join(
            format_channel_reference(guild, channel_id)
            for channel_id in safe_start_channel_ids
        )

    command_role_lines = ["Command roles: Owners/admins only"]
    all_command_role_ids = get_all_command_role_ids(guild.id)
    if all_command_role_ids:
        command_role_lines = ["Command roles:"]
        for command_name in ADMIN_COMMAND_KEYS:
            role_ids = all_command_role_ids.get(command_name, [])
            if not role_ids:
                continue

            command_role_summary = ", ".join(
                format_role_reference(guild, role_id)
                for role_id in role_ids
            )
            command_role_lines.append(
                f"{format_command_reference(command_name)}: {command_role_summary}"
            )

    return [
        "**LinkBot Status**",
        f"Message label: `{message_prefix}`",
        f"Allowed channels: {channel_summary}",
        f"Allowed roles: {role_summary}",
        f"Managed channels: {managed_summary}",
        f"Safe-start channels: {safe_start_summary}",
        f"Logs: `{LOG_FILE}`",
        *command_role_lines,
    ]


async def send_ephemeral(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
        return

    await interaction.response.send_message(message, ephemeral=True)


async def defer_ephemeral(interaction: discord.Interaction) -> None:
    if interaction.response.is_done():
        return

    await interaction.response.defer(ephemeral=True, thinking=True)


async def send_link_message(
    channel: discord.TextChannel | discord.Thread,
    message_prefix: str,
    url: str,
) -> discord.Message:
    return await channel.send(format_link_message(message_prefix, url))


async def safe_delete(message: discord.Message) -> None:
    try:
        await message.delete()
    except discord.NotFound:
        return
    except discord.Forbidden:
        raise
    except discord.HTTPException:
        logger.warning("Failed to delete message %s", message.id)


async def clean_channel(
    channel: discord.TextChannel | discord.Thread,
    keep_message_ids: set[int],
    bot_user_id: int,
    preserve_before_message_id: int | None = None,
) -> int:
    deleted_count = 0

    async for message in channel.history(limit=None, oldest_first=False):
        if preserve_before_message_id is not None and message.id <= preserve_before_message_id:
            continue

        should_keep = message.id in keep_message_ids
        should_keep = should_keep or (
            message.author.id == bot_user_id and get_managed_link_url(message) is not None
        )

        if should_keep:
            continue

        await safe_delete(message)
        deleted_count += 1
        await asyncio.sleep(DELETE_DELAY_SECONDS)

    return deleted_count


async def collect_historical_links(
    channel: discord.TextChannel | discord.Thread,
    bot_user_id: int,
    preserve_before_message_id: int | None = None,
) -> tuple[set[int], list[str]]:
    managed_message_ids: set[int] = set()
    managed_urls: set[str] = set()
    discovered_urls: list[str] = []
    discovered_url_set: set[str] = set()

    async for message in channel.history(limit=None, oldest_first=True):
        if preserve_before_message_id is not None and message.id <= preserve_before_message_id:
            continue

        managed_url = None
        if message.author.id == bot_user_id:
            managed_url = get_managed_link_url(message)

        if managed_url is not None:
            managed_message_ids.add(message.id)
            managed_urls.add(managed_url)
            continue

        for url in extract_urls_from_text(message.content):
            if url in discovered_url_set:
                continue

            discovered_urls.append(url)
            discovered_url_set.add(url)

    links_to_repost: list[str] = []
    seen_urls = set(managed_urls)
    for url in discovered_urls:
        if url in seen_urls:
            continue

        links_to_repost.append(url)
        seen_urls.add(url)

    return managed_message_ids, links_to_repost


def is_initialized_channel(guild_id: int, channel_id: int) -> bool:
    return channel_id in set(get_managed_channel_ids(guild_id))


async def get_channel_boundary_message_id(
    channel: discord.TextChannel | discord.Thread,
) -> int | None:
    async for message in channel.history(limit=1, oldest_first=False):
        return message.id

    return None


async def process_link_submission(
    interaction: discord.Interaction,
    normalized_url: str,
    *,
    safe_first_boot: bool = False,
) -> None:
    guild = interaction.guild
    channel = interaction.channel
    user = interaction.user

    if guild is None or not isinstance(user, discord.Member):
        await send_ephemeral(interaction, "This command only works inside a server.")
        return

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        await send_ephemeral(interaction, "This command only works in text channels and threads.")
        return

    if safe_first_boot and is_initialized_channel(guild.id, channel.id):
        await send_ephemeral(
            interaction,
            "This channel has already been initialized. Use `/safe-link` only as the first LinkBot setup action in a channel.",
        )
        return

    if not safe_first_boot:
        denial_reason = get_link_access_denial_reason(guild, channel, user)
        if denial_reason is not None:
            await send_ephemeral(interaction, denial_reason)
            return

    await defer_ephemeral(interaction)

    message_prefix = get_message_prefix(guild.id)
    preserve_before_message_id = get_preserve_before_message_id(guild.id, channel.id)

    try:
        keep_message_ids: set[int] = set()
        historical_links: list[str] = []
        deleted_count = 0

        if safe_first_boot:
            preserve_before_message_id = await get_channel_boundary_message_id(channel)
        else:
            keep_message_ids, historical_links = await collect_historical_links(
                channel,
                bot_user_id=interaction.client.user.id,
                preserve_before_message_id=preserve_before_message_id,
            )

            for historical_link in historical_links:
                reposted_message = await send_link_message(
                    channel,
                    message_prefix=message_prefix,
                    url=historical_link,
                )
                keep_message_ids.add(reposted_message.id)

        reposted_message = await send_link_message(
            channel,
            message_prefix=message_prefix,
            url=normalized_url,
        )
        keep_message_ids.add(reposted_message.id)

        if safe_first_boot:
            add_managed_channel(
                guild.id,
                channel.id,
                preserve_before_message_id=preserve_before_message_id,
            )
        else:
            deleted_count = await clean_channel(
                channel,
                keep_message_ids=keep_message_ids,
                bot_user_id=interaction.client.user.id,
                preserve_before_message_id=preserve_before_message_id,
            )
            add_managed_channel(guild.id, channel.id)

        logger.info(
            "Processed %s in guild=%s channel=%s user=%s historical_reposted=%s deleted=%s",
            "safe-link" if safe_first_boot else "link",
            guild.id,
            channel.id,
            user.id,
            len(historical_links),
            deleted_count,
        )

        summary = (
            f"Posted your link in {channel.mention}. "
            f"Historical links reposted: {len(historical_links)}. "
            f"Messages removed: {deleted_count}."
        )
        if safe_first_boot:
            summary = (
                f"Safely initialized {channel.mention}. "
                "Earlier channel history was preserved."
            )

        await interaction.followup.send(summary, ephemeral=True)
    except discord.Forbidden:
        logger.warning(
            "Missing permissions while processing %s in guild=%s channel=%s.",
            "safe-link" if safe_first_boot else "link",
            guild.id,
            channel.id,
        )
        await interaction.followup.send(
            "I need `View Channel`, `Send Messages`, `Read Message History`, and `Manage Messages` in this channel.",
            ephemeral=True,
        )


def configure_logging() -> None:
    log_level_name = os.getenv("LINKBOT_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)


class LinkBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.messages = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self) -> None:
        synced_commands = await self.tree.sync()
        logger.info("Synced %s application command(s).", len(synced_commands))


bot = LinkBot()


@bot.event
async def on_ready() -> None:
    logger.info(
        "Logged in as %s (%s) across %s guild(s).",
        bot.user,
        bot.user.id if bot.user else "unknown",
        len(bot.guilds),
    )


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    logger.info("Joined guild %s (%s).", guild.name, guild.id)


@bot.event
async def on_guild_remove(guild: discord.Guild) -> None:
    logger.info("Removed from guild %s (%s).", guild.name, guild.id)


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot or message.guild is None:
        return

    if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
        return

    if not is_managed_link_channel(message.channel):
        return

    try:
        await safe_delete(message)
    except discord.Forbidden:
        logger.warning(
            "Missing permissions while removing invalid message in managed channel guild=%s channel=%s.",
            message.guild.id,
            message.channel.id,
        )
        return

    logger.info(
        "Removed invalid message in managed channel guild=%s channel=%s user=%s.",
        message.guild.id,
        message.channel.id,
        message.author.id,
    )


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.CheckFailure):
        await send_ephemeral(interaction, "You need `Manage Server` to use that command.")
        return

    logger.exception("Unhandled app command error.")
    await send_ephemeral(
        interaction,
        "Something went wrong while running that command. Check `linkbot.log` for details.",
    )


@bot.tree.command(name="link", description="Post a link and clean the current channel.")
@app_commands.describe(url="The link to post")
async def link_command(interaction: discord.Interaction, url: str) -> None:
    normalized_url = normalize_url(url)
    if not is_valid_url(normalized_url):
        await send_ephemeral(
            interaction,
            "That doesn't look like a valid `http://`, `https://`, or `www.` link.",
        )
        return

    await process_link_submission(interaction, normalized_url)


@bot.tree.command(
    name="safe-link",
    description="Initialize a channel without deleting anything that was already there.",
)
@app_commands.guild_only()
@app_commands.describe(url="The first link to post in the safely initialized channel")
async def safe_link_command(interaction: discord.Interaction, url: str) -> None:
    if not isinstance(interaction.user, discord.Member) or not has_command_access(
        interaction.user,
        "safe-link",
    ):
        await send_ephemeral(
            interaction,
            "You need owner/admin access or an allowed role to use `/safe-link`.",
        )
        return

    normalized_url = normalize_url(url)
    if not is_valid_url(normalized_url):
        await send_ephemeral(
            interaction,
            "That doesn't look like a valid `http://`, `https://`, or `www.` link.",
        )
        return

    await process_link_submission(interaction, normalized_url, safe_first_boot=True)


@bot.tree.command(
    name="link-message",
    description="Show or update the label above each reposted link.",
)
@app_commands.guild_only()
@app_commands.describe(message_prefix="Leave blank to see the current label")
async def link_message_command(
    interaction: discord.Interaction,
    message_prefix: str | None = None,
) -> None:
    guild = interaction.guild
    if guild is None:
        await send_ephemeral(interaction, "This command only works inside a server.")
        return

    if not isinstance(interaction.user, discord.Member) or not has_command_access(
        interaction.user,
        "link-message",
    ):
        await send_ephemeral(
            interaction,
            "You need owner/admin access or an allowed role to use `/link-message`.",
        )
        return

    if message_prefix is None:
        await send_ephemeral(
            interaction,
            f"Current link message: `{get_message_prefix(guild.id)}`",
        )
        return

    cleaned_prefix = message_prefix.strip()
    if not cleaned_prefix:
        await send_ephemeral(interaction, "The link message cannot be empty.")
        return

    set_message_prefix(guild.id, cleaned_prefix)
    logger.info(
        "Updated message prefix in guild=%s by user=%s.",
        guild.id,
        interaction.user.id,
    )
    await send_ephemeral(interaction, f"Link message updated to `{cleaned_prefix}`.")


@bot.tree.command(
    name="link-message-reset",
    description="Reset the link label back to the default value.",
)
@app_commands.guild_only()
async def link_message_reset_command(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await send_ephemeral(interaction, "This command only works inside a server.")
        return

    if not isinstance(interaction.user, discord.Member) or not has_command_access(
        interaction.user,
        "link-message-reset",
    ):
        await send_ephemeral(
            interaction,
            "You need owner/admin access or an allowed role to use `/link-message-reset`.",
        )
        return

    reset_message_prefix(guild.id)
    logger.info("Reset message prefix in guild=%s by user=%s.", guild.id, interaction.user.id)
    await send_ephemeral(interaction, f"Link message reset to `{DEFAULT_LINK_MESSAGE}`.")


@bot.tree.command(
    name="link-channel",
    description="List or update the channels where /link is allowed.",
)
@app_commands.guild_only()
@app_commands.describe(
    action="Choose whether to list, add, remove, or clear allowed channels",
    channel="Leave blank to use the current channel for add or remove",
)
@app_commands.choices(action=ACTION_CHOICES)
async def link_channel_command(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    channel: discord.TextChannel | None = None,
) -> None:
    guild = interaction.guild
    current_channel = interaction.channel
    if guild is None or not isinstance(current_channel, (discord.TextChannel, discord.Thread)):
        await send_ephemeral(interaction, "This command only works in server text channels and threads.")
        return

    if not isinstance(interaction.user, discord.Member) or not has_command_access(
        interaction.user,
        "link-channel",
    ):
        await send_ephemeral(
            interaction,
            "You need owner/admin access or an allowed role to use `/link-channel`.",
        )
        return

    if action.value == "list":
        allowed_channel_ids = get_allowed_channel_ids(guild.id)
        if not allowed_channel_ids:
            await send_ephemeral(
                interaction,
                "No channel restrictions are enabled. `/link` works in any text channel.",
            )
            return

        channel_list = ", ".join(
            format_channel_reference(guild, channel_id)
            for channel_id in allowed_channel_ids
        )
        await send_ephemeral(interaction, f"`/link` is allowed in: {channel_list}")
        return

    target_channel_id = channel.id if channel is not None else current_channel.id
    target_channel_reference = format_channel_reference(guild, target_channel_id)

    if action.value == "add":
        if add_allowed_channel(guild.id, target_channel_id):
            logger.info(
                "Added allowed channel guild=%s channel=%s by user=%s.",
                guild.id,
                target_channel_id,
                interaction.user.id,
            )
            await send_ephemeral(interaction, f"`/link` is now allowed in {target_channel_reference}.")
        else:
            await send_ephemeral(
                interaction,
                f"{target_channel_reference} is already in the allowed channel list.",
            )
        return

    if action.value == "remove":
        if remove_allowed_channel(guild.id, target_channel_id):
            logger.info(
                "Removed allowed channel guild=%s channel=%s by user=%s.",
                guild.id,
                target_channel_id,
                interaction.user.id,
            )
            await send_ephemeral(
                interaction,
                f"`/link` is no longer allowed in {target_channel_reference}.",
            )
        else:
            await send_ephemeral(
                interaction,
                f"{target_channel_reference} is not in the allowed channel list.",
            )
        return

    clear_allowed_channels(guild.id)
    logger.info("Cleared allowed channels in guild=%s by user=%s.", guild.id, interaction.user.id)
    await send_ephemeral(interaction, "Channel restrictions cleared. `/link` now works in any text channel.")


@bot.tree.command(
    name="link-role",
    description="List or update the roles allowed to use /link.",
)
@app_commands.guild_only()
@app_commands.describe(
    action="Choose whether to list, add, remove, or clear allowed roles",
    role="The role to add or remove",
)
@app_commands.choices(action=ACTION_CHOICES)
async def link_role_command(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    role: discord.Role | None = None,
) -> None:
    guild = interaction.guild
    if guild is None:
        await send_ephemeral(interaction, "This command only works inside a server.")
        return

    if not isinstance(interaction.user, discord.Member) or not has_command_access(
        interaction.user,
        "link-role",
    ):
        await send_ephemeral(
            interaction,
            "You need owner/admin access or an allowed role to use `/link-role`.",
        )
        return

    if action.value == "list":
        allowed_role_ids = get_allowed_role_ids(guild.id)
        if not allowed_role_ids:
            await send_ephemeral(interaction, "No role restrictions are enabled. Any member can use `/link`.")
            return

        role_list = ", ".join(
            format_role_reference(guild, role_id)
            for role_id in allowed_role_ids
        )
        await send_ephemeral(interaction, f"`/link` is restricted to: {role_list}")
        return

    if action.value in {"add", "remove"} and role is None:
        await send_ephemeral(interaction, "Choose a role for add or remove.")
        return

    if action.value == "add":
        if add_allowed_role(guild.id, role.id):
            logger.info(
                "Added allowed role guild=%s role=%s by user=%s.",
                guild.id,
                role.id,
                interaction.user.id,
            )
            await send_ephemeral(interaction, f"`/link` is now restricted to include {role.mention}.")
        else:
            await send_ephemeral(interaction, f"{role.mention} is already in the allowed role list.")
        return

    if action.value == "remove":
        if remove_allowed_role(guild.id, role.id):
            logger.info(
                "Removed allowed role guild=%s role=%s by user=%s.",
                guild.id,
                role.id,
                interaction.user.id,
            )
            await send_ephemeral(interaction, f"{role.mention} was removed from the allowed role list.")
        else:
            await send_ephemeral(interaction, f"{role.mention} is not in the allowed role list.")
        return

    clear_allowed_roles(guild.id)
    logger.info("Cleared allowed roles in guild=%s by user=%s.", guild.id, interaction.user.id)
    await send_ephemeral(interaction, "Role restrictions cleared. Any member can use `/link` again.")


@bot.tree.command(
    name="link-command-role",
    description="List or update the roles allowed to use LinkBot setup commands.",
)
@app_commands.guild_only()
@app_commands.describe(
    action="Choose whether to list, add, remove, or clear allowed roles for a command",
    command_name="Choose which setup command to manage",
    role="The role to add or remove",
)
@app_commands.choices(action=ACTION_CHOICES, command_name=ADMIN_COMMAND_CHOICES)
async def link_command_role_command(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    command_name: app_commands.Choice[str] | None = None,
    role: discord.Role | None = None,
) -> None:
    guild = interaction.guild
    if guild is None:
        await send_ephemeral(interaction, "This command only works inside a server.")
        return

    if not isinstance(interaction.user, discord.Member) or not is_server_manager(interaction.user):
        await send_ephemeral(
            interaction,
            "Only server owners, administrators, or members with `Manage Server` can change command-role access.",
        )
        return

    if action.value == "list":
        if command_name is None:
            lines = ["**Setup Command Role Access**"]
            command_roles = get_all_command_role_ids(guild.id)
            has_any_entries = False
            for admin_command in ADMIN_COMMAND_KEYS:
                role_ids = command_roles.get(admin_command, [])
                if not role_ids:
                    continue

                has_any_entries = True
                role_summary = ", ".join(
                    format_role_reference(guild, role_id)
                    for role_id in role_ids
                )
                lines.append(f"{format_command_reference(admin_command)}: {role_summary}")

            if not has_any_entries:
                lines.append("Owners/admins only. No extra roles have been granted setup-command access yet.")

            await send_ephemeral(interaction, "\n".join(lines))
            return

        role_ids = get_command_role_ids(guild.id, command_name.value)
        if not role_ids:
            await send_ephemeral(
                interaction,
                f"{format_command_reference(command_name.value)} is currently limited to owners/admins only.",
            )
            return

        role_summary = ", ".join(
            format_role_reference(guild, role_id)
            for role_id in role_ids
        )
        await send_ephemeral(
            interaction,
            f"{format_command_reference(command_name.value)} is also available to: {role_summary}",
        )
        return

    if command_name is None:
        await send_ephemeral(interaction, "Choose a command for add, remove, or clear.")
        return

    if action.value in {"add", "remove"} and role is None:
        await send_ephemeral(interaction, "Choose a role for add or remove.")
        return

    if action.value == "add":
        if add_command_role(guild.id, command_name.value, role.id):
            logger.info(
                "Added command role access guild=%s command=%s role=%s by user=%s.",
                guild.id,
                command_name.value,
                role.id,
                interaction.user.id,
            )
            await send_ephemeral(
                interaction,
                f"{role.mention} can now use {format_command_reference(command_name.value)}.",
            )
        else:
            await send_ephemeral(
                interaction,
                f"{role.mention} already has access to {format_command_reference(command_name.value)}.",
            )
        return

    if action.value == "remove":
        if remove_command_role(guild.id, command_name.value, role.id):
            logger.info(
                "Removed command role access guild=%s command=%s role=%s by user=%s.",
                guild.id,
                command_name.value,
                role.id,
                interaction.user.id,
            )
            await send_ephemeral(
                interaction,
                f"{role.mention} can no longer use {format_command_reference(command_name.value)}.",
            )
        else:
            await send_ephemeral(
                interaction,
                f"{role.mention} does not currently have access to {format_command_reference(command_name.value)}.",
            )
        return

    clear_command_roles(guild.id, command_name.value)
    logger.info(
        "Cleared command role access guild=%s command=%s by user=%s.",
        guild.id,
        command_name.value,
        interaction.user.id,
    )
    await send_ephemeral(
        interaction,
        f"{format_command_reference(command_name.value)} is now limited to owners/admins only.",
    )


@bot.tree.command(
    name="link-status",
    description="Show the current LinkBot configuration for this server.",
)
@app_commands.guild_only()
async def link_status_command(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await send_ephemeral(interaction, "This command only works inside a server.")
        return

    if not isinstance(interaction.user, discord.Member) or not has_command_access(
        interaction.user,
        "link-status",
    ):
        await send_ephemeral(
            interaction,
            "You need owner/admin access or an allowed role to use `/link-status`.",
        )
        return

    await send_ephemeral(interaction, "\n".join(status_lines(guild)))


@bot.tree.command(
    name="link-help",
    description="Show a quick reference for LinkBot's slash commands.",
)
@app_commands.guild_only()
async def link_help_command(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.user, discord.Member) or not has_command_access(
        interaction.user,
        "link-help",
    ):
        await send_ephemeral(
            interaction,
            "You need owner/admin access or an allowed role to use `/link-help`.",
        )
        return

    help_lines = [
        "**LinkBot Commands**",
        "`/link` post a link and clean the current channel",
        "`/safe-link` safely initialize a channel without touching earlier history",
        "`/link-message` show or set the label above reposted links",
        "`/link-message-reset` restore the default label",
        "`/link-channel` list, add, remove, or clear allowed channels",
        "`/link-role` list, add, remove, or clear allowed roles",
        "`/link-command-role` delegate setup-command access to specific roles",
        "`/link-status` show the current server settings",
        "`/link-help` show this help message",
        "Owners/admins always keep full access, and can delegate setup commands to additional roles with `/link-command-role`.",
    ]
    await send_ephemeral(interaction, "\n".join(help_lines))


def main() -> None:
    load_dotenv()
    configure_logging()

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing DISCORD_BOT_TOKEN in environment or .env file.")

    logger.info("Starting LinkBot.")
    bot.run(token)


if __name__ == "__main__":
    main()
