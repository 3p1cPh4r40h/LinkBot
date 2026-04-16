import asyncio
import json
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Any, Final
from urllib.parse import urlparse

import discord
from discord.ext import commands
from dotenv import load_dotenv


COMMAND_PREFIX: Final[str] = "!"
DELETE_DELAY_SECONDS: Final[float] = 0.4
DEFAULT_LINK_MESSAGE: Final[str] = "New Link"
DEFAULT_REPLY_DELETE_AFTER: Final[float] = 10
SETTINGS_FILE: Final[str] = "guild_settings.json"
LOG_FILE: Final[str] = "linkbot.log"
LOG_MAX_BYTES: Final[int] = 1_000_000
LOG_BACKUP_COUNT: Final[int] = 3
URL_PATTERN: Final[re.Pattern[str]] = re.compile(r"https?://\S+")

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
        }
        return guild_settings[guild_key]

    guild_config = guild_settings[guild_key]
    guild_config.setdefault("message_prefix", DEFAULT_LINK_MESSAGE)
    guild_config.setdefault("allowed_channel_ids", [])
    guild_config.setdefault("allowed_role_ids", [])
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


def normalize_url(value: str) -> str:
    return value.strip().strip("<>").rstrip(".,!?)")


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


def current_channel_ids(channel: discord.abc.GuildChannel | discord.Thread) -> set[int]:
    channel_ids = {channel.id}
    if isinstance(channel, discord.Thread) and channel.parent_id is not None:
        channel_ids.add(channel.parent_id)

    return channel_ids


def get_link_access_denial_reason(ctx: commands.Context) -> str | None:
    if ctx.guild is None:
        return "This command only works in server channels."

    if not isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
        return "This command only works in text channels and threads."

    if is_server_manager(ctx.author):
        return None

    allowed_channel_ids = set(get_allowed_channel_ids(ctx.guild.id))
    if allowed_channel_ids and not (current_channel_ids(ctx.channel) & allowed_channel_ids):
        allowed_channels = ", ".join(
            format_channel_reference(ctx.guild, channel_id)
            for channel_id in sorted(allowed_channel_ids)
        )
        return f"`!link` is only enabled in: {allowed_channels}"

    allowed_role_ids = set(get_allowed_role_ids(ctx.guild.id))
    if allowed_role_ids and isinstance(ctx.author, discord.Member):
        author_role_ids = {role.id for role in ctx.author.roles}
        if not (author_role_ids & allowed_role_ids):
            allowed_roles = ", ".join(
                format_role_reference(ctx.guild, role_id)
                for role_id in sorted(allowed_role_ids)
            )
            return f"You need one of these roles to use `!link`: {allowed_roles}"

    return None


def status_lines(guild: discord.Guild) -> list[str]:
    message_prefix = get_message_prefix(guild.id)
    allowed_channel_ids = get_allowed_channel_ids(guild.id)
    allowed_role_ids = get_allowed_role_ids(guild.id)

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

    return [
        "**LinkBot Status**",
        f"Message label: `{message_prefix}`",
        f"Allowed channels: {channel_summary}",
        f"Allowed roles: {role_summary}",
        f"Logs: `{LOG_FILE}`",
    ]


async def reply_temp(
    ctx: commands.Context,
    message: str,
    *,
    delete_after: float | None = DEFAULT_REPLY_DELETE_AFTER,
) -> None:
    await ctx.reply(message, mention_author=False, delete_after=delete_after)


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
) -> int:
    deleted_count = 0

    async for message in channel.history(limit=None, oldest_first=False):
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
    skip_message_ids: set[int] | None = None,
) -> tuple[set[int], list[str]]:
    managed_message_ids: set[int] = set()
    managed_urls: set[str] = set()
    discovered_urls: list[str] = []
    discovered_url_set: set[str] = set()
    skip_ids = skip_message_ids or set()

    async for message in channel.history(limit=None, oldest_first=True):
        if message.id in skip_ids:
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


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)


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
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        usage_by_command = {
            "link": "`!link https://example.com`",
            "link-channel": "`!link-channel add #links`, `!link-channel remove #links`, or `!link-channel clear`",
            "link-role": "`!link-role add @role`, `!link-role remove @role`, or `!link-role clear`",
        }
        usage = usage_by_command.get(ctx.command.name if ctx.command else "", "`!link-help`")
        await reply_temp(ctx, f"Missing `{error.param.name}`. Try {usage}.")
        return

    if isinstance(error, commands.BadArgument):
        await reply_temp(ctx, "I couldn't parse that command. Try `!link-help` for examples.")
        return

    logger.exception("Unhandled command error in %s.", ctx.command.qualified_name if ctx.command else "unknown")
    await reply_temp(ctx, "Something went wrong while running that command. Check `linkbot.log` for details.")


@bot.command(name="link-help")
async def link_help(ctx: commands.Context) -> None:
    help_lines = [
        "**LinkBot Commands**",
        "`!link <url>` repost a link and clean the channel",
        "`!link-message` show the current label",
        "`!link-message <text>` set the label above each reposted link",
        f"`!link-message-reset` restore the label to `{DEFAULT_LINK_MESSAGE}`",
        "`!link-channel list|add|remove|clear [#channel]` control where `!link` can be used",
        "`!link-role list|add|remove|clear [@role]` control which roles can use `!link`",
        "`!link-status` show the current server settings",
        "`!link-help` show this help message",
        "Admins with `Manage Server` can always use the bot, even if channel or role restrictions are enabled.",
    ]
    await ctx.reply("\n".join(help_lines), mention_author=False)


@bot.command(name="link-status")
async def link_status(ctx: commands.Context) -> None:
    if ctx.guild is None:
        await reply_temp(ctx, "This command only works inside a server.")
        return

    await ctx.reply("\n".join(status_lines(ctx.guild)), mention_author=False)


@bot.command(name="link")
async def link(ctx: commands.Context, *, url: str) -> None:
    denial_reason = get_link_access_denial_reason(ctx)
    if denial_reason is not None:
        await reply_temp(ctx, denial_reason)
        return

    if not isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
        await reply_temp(ctx, "This command only works in text channels and threads.")
        return

    normalized_url = normalize_url(url)
    if not is_valid_url(normalized_url):
        await reply_temp(ctx, "That doesn't look like a valid `http://` or `https://` link.")
        return

    message_prefix = get_message_prefix(ctx.guild.id if ctx.guild else None)

    try:
        keep_message_ids, historical_links = await collect_historical_links(
            ctx.channel,
            bot_user_id=ctx.bot.user.id,
            skip_message_ids={ctx.message.id},
        )

        for historical_link in historical_links:
            reposted_message = await send_link_message(
                ctx.channel,
                message_prefix=message_prefix,
                url=historical_link,
            )
            keep_message_ids.add(reposted_message.id)

        reposted_message = await send_link_message(
            ctx.channel,
            message_prefix=message_prefix,
            url=normalized_url,
        )
        keep_message_ids.add(reposted_message.id)

        deleted_count = await clean_channel(
            ctx.channel,
            keep_message_ids=keep_message_ids,
            bot_user_id=ctx.bot.user.id,
        )

        logger.info(
            "Processed link in guild=%s channel=%s user=%s url=%s historical_reposted=%s deleted=%s",
            ctx.guild.id if ctx.guild else "dm",
            ctx.channel.id,
            ctx.author.id,
            normalized_url,
            len(historical_links),
            deleted_count,
        )
    except discord.Forbidden:
        logger.warning(
            "Missing permissions while processing link in guild=%s channel=%s.",
            ctx.guild.id if ctx.guild else "dm",
            ctx.channel.id,
        )
        await reply_temp(
            ctx,
            "I need `View Channel`, `Send Messages`, `Read Message History`, and `Manage Messages` in this channel.",
        )


@bot.command(name="link-message")
async def link_message(ctx: commands.Context, *, message_prefix: str | None = None) -> None:
    if ctx.guild is None:
        await reply_temp(ctx, "This command only works inside a server.")
        return

    if message_prefix is None:
        await reply_temp(
            ctx,
            f"Current link message: `{get_message_prefix(ctx.guild.id)}`",
            delete_after=15,
        )
        return

    if not is_server_manager(ctx.author):
        await reply_temp(ctx, "You need `Manage Server` to change the link message.")
        return

    cleaned_prefix = message_prefix.strip()
    if not cleaned_prefix:
        await reply_temp(ctx, "The link message cannot be empty.")
        return

    set_message_prefix(ctx.guild.id, cleaned_prefix)
    logger.info(
        "Updated message prefix in guild=%s by user=%s to %r.",
        ctx.guild.id,
        ctx.author.id,
        cleaned_prefix,
    )
    await reply_temp(ctx, f"Link message updated to `{cleaned_prefix}`.")


@bot.command(name="link-message-reset")
async def link_message_reset(ctx: commands.Context) -> None:
    if ctx.guild is None:
        await reply_temp(ctx, "This command only works inside a server.")
        return

    if not is_server_manager(ctx.author):
        await reply_temp(ctx, "You need `Manage Server` to reset the link message.")
        return

    reset_message_prefix(ctx.guild.id)
    logger.info("Reset message prefix in guild=%s by user=%s.", ctx.guild.id, ctx.author.id)
    await reply_temp(ctx, f"Link message reset to `{DEFAULT_LINK_MESSAGE}`.")


@bot.command(name="link-channel")
async def link_channel(
    ctx: commands.Context,
    action: str = "list",
    channel: discord.TextChannel | None = None,
) -> None:
    if ctx.guild is None:
        await reply_temp(ctx, "This command only works inside a server.")
        return

    normalized_action = action.lower()
    if normalized_action == "list":
        allowed_channel_ids = get_allowed_channel_ids(ctx.guild.id)
        if not allowed_channel_ids:
            await reply_temp(ctx, "No channel restrictions are enabled. `!link` works in any text channel.")
            return

        channel_list = ", ".join(
            format_channel_reference(ctx.guild, channel_id)
            for channel_id in allowed_channel_ids
        )
        await reply_temp(ctx, f"`!link` is allowed in: {channel_list}", delete_after=15)
        return

    if not is_server_manager(ctx.author):
        await reply_temp(ctx, "You need `Manage Server` to change channel permissions.")
        return

    target_channel_id = channel.id if channel is not None else ctx.channel.id
    target_channel_reference = format_channel_reference(ctx.guild, target_channel_id)

    if normalized_action == "add":
        if add_allowed_channel(ctx.guild.id, target_channel_id):
            logger.info(
                "Added allowed channel guild=%s channel=%s by user=%s.",
                ctx.guild.id,
                target_channel_id,
                ctx.author.id,
            )
            await reply_temp(ctx, f"`!link` is now allowed in {target_channel_reference}.")
        else:
            await reply_temp(ctx, f"{target_channel_reference} is already in the allowed channel list.")
        return

    if normalized_action == "remove":
        if remove_allowed_channel(ctx.guild.id, target_channel_id):
            logger.info(
                "Removed allowed channel guild=%s channel=%s by user=%s.",
                ctx.guild.id,
                target_channel_id,
                ctx.author.id,
            )
            await reply_temp(ctx, f"`!link` is no longer allowed in {target_channel_reference}.")
        else:
            await reply_temp(ctx, f"{target_channel_reference} is not in the allowed channel list.")
        return

    if normalized_action == "clear":
        clear_allowed_channels(ctx.guild.id)
        logger.info("Cleared allowed channels in guild=%s by user=%s.", ctx.guild.id, ctx.author.id)
        await reply_temp(ctx, "Channel restrictions cleared. `!link` now works in any text channel.")
        return

    await reply_temp(ctx, "Use `!link-channel list`, `add`, `remove`, or `clear`.")


@bot.command(name="link-role")
async def link_role(
    ctx: commands.Context,
    action: str = "list",
    role: discord.Role | None = None,
) -> None:
    if ctx.guild is None:
        await reply_temp(ctx, "This command only works inside a server.")
        return

    normalized_action = action.lower()
    if normalized_action == "list":
        allowed_role_ids = get_allowed_role_ids(ctx.guild.id)
        if not allowed_role_ids:
            await reply_temp(ctx, "No role restrictions are enabled. Any member can use `!link`.")
            return

        role_list = ", ".join(
            format_role_reference(ctx.guild, role_id)
            for role_id in allowed_role_ids
        )
        await reply_temp(ctx, f"`!link` is restricted to: {role_list}", delete_after=15)
        return

    if not is_server_manager(ctx.author):
        await reply_temp(ctx, "You need `Manage Server` to change role permissions.")
        return

    if normalized_action in {"add", "remove"} and role is None:
        await reply_temp(ctx, "Mention a role, for example `!link-role add @Mods`.")
        return

    if normalized_action == "add":
        if add_allowed_role(ctx.guild.id, role.id):
            logger.info(
                "Added allowed role guild=%s role=%s by user=%s.",
                ctx.guild.id,
                role.id,
                ctx.author.id,
            )
            await reply_temp(ctx, f"`!link` is now restricted to include {role.mention}.")
        else:
            await reply_temp(ctx, f"{role.mention} is already in the allowed role list.")
        return

    if normalized_action == "remove":
        if remove_allowed_role(ctx.guild.id, role.id):
            logger.info(
                "Removed allowed role guild=%s role=%s by user=%s.",
                ctx.guild.id,
                role.id,
                ctx.author.id,
            )
            await reply_temp(ctx, f"{role.mention} was removed from the allowed role list.")
        else:
            await reply_temp(ctx, f"{role.mention} is not in the allowed role list.")
        return

    if normalized_action == "clear":
        clear_allowed_roles(ctx.guild.id)
        logger.info("Cleared allowed roles in guild=%s by user=%s.", ctx.guild.id, ctx.author.id)
        await reply_temp(ctx, "Role restrictions cleared. Any member can use `!link` again.")
        return

    await reply_temp(ctx, "Use `!link-role list`, `add`, `remove`, or `clear`.")


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
