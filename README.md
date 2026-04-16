# LinkBot

`LinkBot` is a small Discord bot that watches for `!link <url>`, reposts the link as the bot, and then deletes the rest of the messages in that channel so only bot-posted links remain.

## What It Does

- Accepts commands like `!link https://example.com`
- Reposts the URL as the bot
- Deletes the original command message
- Deletes other non-link messages in that channel
- Keeps previously reposted bot link messages so the channel stays as a clean link list

## Requirements

- Python 3.11+ recommended
- A Discord application with a bot user
- The bot invited to your server with these permissions in the target channel:
  - `View Channel`
  - `Send Messages`
  - `Read Message History`
  - `Manage Messages`

You also need to enable the **Message Content Intent** for the bot in the Discord Developer Portal, because the bot reads `!link` messages.

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example environment file and add your bot token:

```bash
cp .env.example .env
```

Then edit `.env` and set:

```env
DISCORD_BOT_TOKEN=your_actual_token_here
```

## Running The Bot

Start the bot with:

```bash
python3 bot.py
```

If login succeeds, the bot will stay online and listen for `!link` commands.

## How To Use It

In a Discord channel where the bot has access, send:

```text
!link https://example.com
```

The bot will:

1. Post `https://example.com`
2. Remove your original `!link` message
3. Remove other messages in that channel that are not bot-posted link messages

The result is a channel that only contains links reposted by the bot.

## Important Notes

- The bot only treats `http://` and `https://` values as valid links.
- If the bot does not have `Manage Messages`, it can repost links but will not be able to clean the channel.
- Deleting a large number of old messages can take a little time because Discord rate-limits message deletion.
- This bot currently uses the `!link` prefix command style, not slash commands.

## Files

- `bot.py`: the bot source code
- `requirements.txt`: Python dependencies
- `.env.example`: example environment variables

## Future Ideas

- Restrict cleanup to specific channels
- Add slash command support
- Store an allowlist of channels or roles
- Add logging to a file
