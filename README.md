# LinkBot

LinkBot turns a Discord channel into a clean, bot-managed list of links.

When someone posts `!link https://example.com`, the bot reposts the link in a consistent format, preserves older links it finds in channel history, and removes the surrounding clutter so the channel stays tidy.

## Add LinkBot To Your Server

LinkBot is already hosted, so most server owners do not need to run any code.

Invite Link:

https://discord.com/oauth2/authorize?client_id=1494387968796917882&permissions=68608&integration_type=0&scope=bot+applications.commands

1. Open the bot invite link for your hosted LinkBot deployment.
2. Choose your server.
3. Approve the requested permissions.
4. Add the bot to a test channel first, not a busy production channel.
5. In Discord, run `!link-help` to see the available commands.
6. Lock usage to one channel or one role before wider rollout.

If you want to share LinkBot with someone else, send them the invite link above.

## Safe Setup First

LinkBot deletes messages as part of its cleanup flow, so treat the first setup like a moderation tool rollout.

Recommended first-time setup:

1. Create a dedicated channel such as `#links`.
2. Give LinkBot `Manage Messages` only in that channel if possible.
3. Run `!link-channel add #links` right away.
4. Optionally run `!link-role add @Moderators` so only a trusted role can trigger cleanup.
5. Test with a few sample messages before letting regular members use it.

This is the safest default because it prevents someone from using `!link` in the wrong place before restrictions are configured.

## Recommended Bot Permissions

In channels where LinkBot will run, it should have:

- `View Channel`
- `Send Messages`
- `Read Message History`
- `Manage Messages`

Without `Manage Messages`, the bot can still repost links, but it will not be able to fully clean the channel.

### Strong Permission Recommendation

If you want to reduce risk, do not give LinkBot broad `Manage Messages` access across your whole server.

Instead:

- Create one dedicated links channel
- Give the bot its full permissions only there
- Leave the bot without cleanup permissions in other channels
- Use `!link-channel add #your-links-channel` to match the Discord permission setup

## What LinkBot Does

- Reposts links in a clean bot-owned format
- Preserves historical links during the first cleanup instead of wiping them out
- Lets server admins customize the label above each link
- Supports per-server channel restrictions
- Supports per-server role restrictions

## What A Reposted Link Looks Like

By default, LinkBot posts:

```text
New Link
https://example.com
```

Admins can change `New Link` to something else with a command.

## Everyday Use

Post a link:

```text
!link https://example.com
```

The bot will:

1. Repost the link using the current label
2. Repost older links it finds in that channel if they have not already been preserved
3. Remove non-link clutter from the channel

That cleanup behavior is intentional, so only use `!link` in channels you are comfortable having cleaned.

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

## Important Safety Notes

- The first time `!link` is used in a channel, LinkBot may repost older links it finds there and remove other messages it does not preserve
- LinkBot is designed for dedicated link collection channels, not general chat channels
- Deleted messages are not recoverable through the bot
- If you do not restrict channels, someone could run `!link` in the wrong place
- If you do not restrict roles, any member can trigger cleanup unless Discord channel permissions stop them
- Always test in a small channel first before using it in an important server channel
- Check `!link-status` after setup so you can confirm the active restrictions

## Self-Hosting

If you would rather run your own copy, the files in this repo are still available for self-hosting.

### Self-Hosting Requirements

- Python 3.11 or newer
- A Discord application with a bot user
- The **Message Content Intent** enabled in the Discord Developer Portal

### Self-Hosting Quick Start

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
- The safest setup is one dedicated links channel plus channel and role restrictions
