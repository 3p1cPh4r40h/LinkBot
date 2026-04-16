import asyncio
import logging
import os
from typing import Final
from urllib.parse import urlparse

import discord
from discord.ext import commands
from dotenv import load_dotenv


COMMAND_PREFIX: Final[str] = "!"
DELETE_DELAY_SECONDS: Final[float] = 0.4


def is_valid_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_pure_link_message(message: discord.Message) -> bool:
    content = message.content.strip()
    return bool(content) and is_valid_url(content)


async def safe_delete(message: discord.Message) -> None:
    try:
        await message.delete()
    except discord.NotFound:
        return
    except discord.Forbidden:
        raise
    except discord.HTTPException:
        logging.warning("Failed to delete message %s", message.id)


async def clean_channel(
    channel: discord.TextChannel | discord.Thread,
    keep_message_ids: set[int],
    bot_user_id: int,
) -> None:
    async for message in channel.history(limit=None, oldest_first=False):
        should_keep = message.id in keep_message_ids
        should_keep = should_keep or (
            message.author.id == bot_user_id and is_pure_link_message(message)
        )

        if should_keep:
            continue

        await safe_delete(message)
        await asyncio.sleep(DELETE_DELAY_SECONDS)


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


@bot.event
async def on_ready() -> None:
    logging.info("Logged in as %s (%s)", bot.user, bot.user.id if bot.user else "unknown")


@bot.command(name="link")
async def link(ctx: commands.Context, *, url: str) -> None:
    if not isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
        return

    normalized_url = url.strip().strip("<>")

    if not is_valid_url(normalized_url):
        await ctx.reply(
            "That doesn't look like a valid `http://` or `https://` link.",
            mention_author=False,
            delete_after=8,
        )
        return

    reposted_message = await ctx.send(normalized_url)

    try:
        await clean_channel(
            ctx.channel,
            keep_message_ids={reposted_message.id},
            bot_user_id=ctx.bot.user.id,
        )
    except discord.Forbidden:
        await ctx.send(
            "I need `Manage Messages`, `Read Message History`, and `Send Messages` in this channel.",
            delete_after=10,
        )


def main() -> None:
    load_dotenv()

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing DISCORD_BOT_TOKEN in environment or .env file.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bot.run(token)


if __name__ == "__main__":
    main()
