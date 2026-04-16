# LinkBot

LinkBot turns a Discord channel into a clean, bot-managed list of links using slash commands.

Use `/link` to post a link in a polished format, keep a channel tidy, and maintain a consistent link feed for your server.

## Add LinkBot To Your Server

LinkBot is already hosted, so most server owners do not need to run any code.

Invite Link:

https://discord.com/oauth2/authorize?client_id=1494387968796917882&permissions=68608&integration_type=0&scope=bot+applications.commands

1. Open the invite link above.
2. Choose your server.
3. Approve the requested permissions.
4. Wait a short moment for slash commands to appear.
5. Start in a test channel, not a busy production channel.
6. Run `/link-help` in Discord to see the command list.
7. Lock usage to one channel or one role before wider rollout.

If you want to share LinkBot with someone else, send them the invite link above.

## Safe Setup First

LinkBot can delete messages as part of its cleanup flow, so treat the first setup like a moderation tool rollout.

Recommended first-time setup:

1. Create a dedicated channel such as `#links`.
2. Give LinkBot `Manage Messages` only in that channel if possible.
3. Run `/link-channel` with `action: Add` and `channel: #links`.
4. Optionally run `/link-role` with `action: Add` and a trusted role such as `@Moderators`.
5. Use `/safe-link` as the very first LinkBot setup action in that channel.
6. Test with a few sample messages before letting regular members use it.

This is the safest default because it prevents someone from using `/link` in the wrong place before restrictions are configured.

### Why `/safe-link` Exists

`/safe-link` is the safe first-boot option for a channel.

- It posts the link you give it
- It marks the channel as managed by LinkBot
- It does not delete or rewrite any messages that were already in the channel
- It preserves everything that was sent before that first `/safe-link`

Use `/safe-link` only once, as the first LinkBot setup action in a channel. After a channel has already been initialized, use normal `/link` commands going forward.

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
- Use `/link-channel` to match the Discord permission setup

## What LinkBot Does

- Reposts links in a clean bot-owned format
- Offers a safe first-boot mode with `/safe-link` that preserves all earlier channel history
- Preserves historical links during normal first cleanup instead of wiping them out
- After a channel is initialized, watches new messages there and removes anything that is not a LinkBot-managed post
- Lets server admins customize the label above each link
- Supports per-server channel restrictions
- Supports per-server role restrictions

## What A Reposted Link Looks Like

By default, LinkBot posts:

```text
New Link
https://example.com
```

Admins can change `New Link` with `/link-message`.

## Everyday Use

Post a link with:

```text
/link url:https://example.com
```

Safely initialize a channel with:

```text
/safe-link url:https://example.com
```

Normal `/link` behavior:

1. Reposts the link using the current label
2. Reposts older links it finds in that channel if they have not already been preserved
3. Marks that channel as managed for future moderation
4. Removes non-link clutter from the channel

Safe `/safe-link` behavior:

1. Reposts the link using the current label
2. Marks that channel as managed
3. Preserves everything that was already in the channel
4. Starts enforcing LinkBot-only posting from that point onward

After a channel has been initialized, new regular messages in that channel are removed automatically.

## Slash Commands

These are the commands server owners and admins will use most often.

### `/link`

Post a link and clean the current channel.

Example:

```text
/link url:https://example.com
```

### `/safe-link`

Safely initialize a channel without deleting earlier history.

Example:

```text
/safe-link url:https://example.com
```

Important:

- Only server managers should use it
- It is intended for the first LinkBot setup action in a channel
- It will not clean older messages that were already there
- After it succeeds, that channel becomes managed going forward

### `/link-message`

Show the current label or set a new one.

Examples:

```text
/link-message
/link-message message_prefix:Fresh Drop
```

### `/link-message-reset`

Reset the label back to the default.

### `/link-channel`

List or update the channels where `/link` is allowed.

Examples:

```text
/link-channel action:List
/link-channel action:Add channel:#links
/link-channel action:Remove channel:#links
/link-channel action:Clear
```

### `/link-role`

List or update the roles allowed to use `/link`.

Examples:

```text
/link-role action:List
/link-role action:Add role:@Moderators
/link-role action:Remove role:@Moderators
/link-role action:Clear
```

### `/link-status`

Show the current server configuration.

### `/link-help`

Show a quick command reference.

## Permission Behavior

- If no channels are configured, `/link` can be used in any text channel
- If no roles are configured, any member can use `/link`
- If channel restrictions are set, `/link` only works in those channels
- If role restrictions are set, `/link` only works for members with one of those roles
- Members with `Manage Server` or `Administrator` can always configure and use the bot
- Admin and config responses are shown as ephemeral slash-command replies, which keeps setup clean in-channel

## Important Safety Notes

- `/safe-link` is the safest first command for a channel because it preserves all earlier history
- The first time normal `/link` is used in a channel, LinkBot may repost older links it finds there and remove other messages it does not preserve
- After the first successful `/link` in a channel, LinkBot actively moderates new messages there
- After the first successful `/safe-link` in a channel, LinkBot actively moderates new messages there while leaving older history alone
- LinkBot is designed for dedicated link collection channels, not general chat channels
- Deleted messages are not recoverable through the bot
- If you do not restrict channels, someone could use `/link` in the wrong place
- If you do not restrict roles, any member can trigger cleanup unless Discord channel permissions stop them
- Always test in a small channel first before using it in an important server channel
- Check `/link-status` after setup so you can confirm the active restrictions

## Logging

LinkBot writes logs to `linkbot.log`.

- Logs rotate automatically
- Older log files are kept as backups
- You can change the log level with `LINKBOT_LOG_LEVEL`
- Logs do not store raw user message bodies
- Logs do not store submitted link URLs

What each level is used for:

- `DEBUG` for verbose operational diagnostics such as internal state checks and troubleshooting details
- `INFO` for normal bot lifecycle and moderation events such as startup, guild join or leave events, settings changes, command sync, and counts of reposted or deleted messages
- `WARNING` for recoverable problems such as missing permissions
- `ERROR` for unexpected failures and stack traces

## Self-Hosting

If you would rather run your own copy, the files in this repo are still available for self-hosting.

### Self-Hosting Requirements

- Python 3.11 or newer
- A Discord application with a bot user
- The `applications.commands` scope enabled in the invite flow
- The **Message Content Intent** enabled in the Discord Developer Portal

Why Message Content is still needed:

LinkBot scans existing channel history to preserve and repost previously shared links during cleanup. Discord treats message content as privileged data, so self-hosted copies still need the Message Content Intent even though commands are now slash commands.

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

## Files

- `bot.py` - the bot source code
- `requirements.txt` - Python dependencies
- `.env.example` - example environment variables
- `guild_settings.json` - created automatically for saved server settings
- `linkbot.log` - created automatically for runtime logs

## Notes

- The bot accepts `http://`, `https://`, and `www.` links, and automatically converts `www.` links to `https://...`
- This bot uses slash commands instead of prefix commands
- Global slash command updates can take a little time to appear after deployment
- Large cleanups can take a little time because Discord rate-limits message deletion
- The safest setup is one dedicated links channel plus channel and role restrictions
