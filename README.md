# LinkBot

LinkBot turns a Discord channel into a clean, bot-managed list of links.

When someone posts `!link https://example.com`, the bot reposts the link in a consistent format, preserves older links it finds in channel history, and removes the surrounding clutter so the channel stays tidy.

## Features

- Reposts links in a clean bot-owned format
- Preserves historical links during the first cleanup instead of wiping them out
- Lets server admins customize the label above each link
- Supports per-server channel restrictions
- Supports per-server role restrictions
- Stores server settings automatically in `guild_settings.json`
- Writes rotating logs to `linkbot.log`

## What A Reposted Link Looks Like

By default, LinkBot posts:

```text
New Link
https://example.com
```

Admins can change `New Link` to something else with a command.

## Requirements

- Python 3.11 or newer
- A Discord application with a bot user
- The bot invited to your server
- The **Message Content Intent** enabled in the Discord Developer Portal

### Bot Permissions

In channels where the bot will run, it should have:

- `View Channel`
- `Send Messages`
- `Read Message History`
- `Manage Messages`

Without `Manage Messages`, the bot can still repost links, but it will not be able to fully clean the channel.

## Quick Start

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example environment file:

```bash
cp .env.example .env
```

4. Edit `.env` and set your bot token:

```env
DISCORD_BOT_TOKEN=your_actual_token_here
LINKBOT_LOG_LEVEL=INFO
```

5. Start the bot:

```bash
python3 bot.py
```

## Everyday Use

Post a link:

```text
!link https://example.com
```

The bot will:

1. Repost the link using the current label
2. Repost older links it finds in that channel if they have not already been preserved
3. Remove non-link clutter from the channel

## Admin Commands

These are the commands server owners and admins will use most often.

### `!link-message`

Show the current label:

```text
!link-message
```

Set the label above each reposted link:

```text
!link-message Fresh Drop
```

Reset it back to the default:

```text
!link-message-reset
```

### `!link-channel`

Allow `!link` in a specific channel:

```text
!link-channel add #links
```

Remove a channel from the allowlist:

```text
!link-channel remove #links
```

Show the current channel allowlist:

```text
!link-channel list
```

Clear channel restrictions so `!link` works anywhere:

```text
!link-channel clear
```

If you leave off the channel on `add` or `remove`, the bot uses the current channel.

### `!link-role`

Restrict `!link` to a role:

```text
!link-role add @Moderators
```

Remove a role restriction:

```text
!link-role remove @Moderators
```

Show the current role allowlist:

```text
!link-role list
```

Clear role restrictions so anyone can use `!link`:

```text
!link-role clear
```

### `!link-status`

Show the current server configuration:

```text
!link-status
```

### `!link-help`

Show a quick command reference:

```text
!link-help
```

## Permission Behavior

- If no channels are configured, `!link` can be used in any text channel
- If no roles are configured, any member can use `!link`
- If channel restrictions are set, `!link` only works in those channels
- If role restrictions are set, `!link` only works for members with one of those roles
- Members with `Manage Server` or `Administrator` can always configure and use the bot

## Logging

LinkBot writes logs to `linkbot.log`.

- Logs rotate automatically
- Older log files are kept as backups
- You can change the log level with `LINKBOT_LOG_LEVEL`

Useful values include:

- `DEBUG`
- `INFO`
- `WARNING`
- `ERROR`

## Files

- `bot.py` - the bot source code
- `requirements.txt` - Python dependencies
- `.env.example` - example environment variables
- `guild_settings.json` - created automatically for saved server settings
- `linkbot.log` - created automatically for runtime logs

## Notes

- The bot only accepts `http://` and `https://` links
- This bot currently uses prefix commands instead of slash commands
- Large cleanups can take a little time because Discord rate-limits message deletion

## Nice Next Steps

If you want to keep improving this bot later, good next additions would be:

- Slash commands
- Docker packaging
- A hosted multi-server deployment
- A per-channel on or off switch instead of a simple allowlist
