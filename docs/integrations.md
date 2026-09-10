# Integrations Guide: Issue Trackers & Messaging

This guide explains how to connect and configure issue trackers (Linear, GitHub) and messaging tools (Slack) in `px0`, including how to generate tokens and permissions.

---

## 1. Linear Integration

px0 uses the Linear GraphQL API for fetching issues, managing states, and triaging tickets.

### How to generate a Linear API Key
1. Sign in to your Linear account at [linear.app](https://linear.app).
2. Click your profile avatar (bottom-left) and select **Settings** -> **Account** -> **API** (or go directly to [linear.app/settings/account/api](https://linear.app/settings/account/api)).
3. Under **Personal API keys**, click **Create key**.
4. Enter a label (for example, `px0`), and click **Create**.
5. Copy the generated API key (it begins with `lin_api_...`).

### How to configure in px0
- **During `px0 init`:** Select `Linear` when prompted, and paste your API key.
- **Manually:** Add it to your credentials file (`~/.px0/.state/credentials.toml`):
  ```toml
  [linear]
  api_key = "lin_api_..."
  ```
  Or export the environment variable:
  ```shell
  export LINEAR_API_KEY="lin_api_..."
  ```

---

## 2. GitHub Integration

px0 connects to GitHub for issue tracking, review queue workflows, and repository queries.

### How to generate a GitHub Personal Access Token (PAT)
1. Sign in to GitHub and go to [github.com/settings/tokens](https://github.com/settings/tokens).
2. Choose **Tokens (classic)** or **Fine-grained personal access tokens**:
   - **Classic Token (Recommended for full automation):**
     - Click **Generate new token (classic)**.
     - Note/Description: `px0`.
     - Expiration: Choose desired lifetime.
     - Scopes: Check `repo` (Full control of private repositories and issues). For public repos only, check `public_repo`.
     - Click **Generate token** and copy it (`ghp_...`).
   - **Fine-grained Token:**
     - Select target repository access.
     - Under Repository permissions, grant **Issues** (Read & Write) and **Pull Requests** (Read & Write).
3. Copy the generated token immediately.

### How to configure in px0
- **During `px0 init`:** Select `GitHub` when prompted, and paste your token.
- **Manually:** Add it to your credentials file (`~/.px0/.state/credentials.toml`):
  ```toml
  [github]
  token = "ghp_..."
  ```
  Or export the environment variable:
  ```shell
  export GITHUB_TOKEN="ghp_..."
  ```

---

## 3. Slack Integration

px0 provides Slack messaging capabilities via `tpt.messaging`: posting channel messages, replying in threads, following discussions, retrieving `@mentions`, and reacting with emoji.

### How to generate a Slack Bot Token
1. Go to the [Slack API App Console](https://api.slack.com/apps).
2. Click **Create New App** -> **From scratch**.
3. Name your app (e.g. `px0-bot`) and select your Slack workspace.
4. Navigate to **OAuth & Permissions** in the left sidebar.
5. Scroll down to **Scopes** -> **Bot Token Scopes** and add:
   - `chat:write` — Post messages and replies.
   - `channels:read` — View public channels.
   - `groups:read` — View private channels the bot is added to.
   - `channels:history` — View messages and thread replies in public channels.
   - `groups:history` — View messages in private channels.
   - `app_mentions:read` — Read mentions of your bot (`@bot`).
   - `reactions:write` — Add emoji reactions.
   - `reactions:read` — View reactions on messages.
   - `search:read` (Optional, requires User Token) — Search workspace messages.
6. Scroll up to the top of **OAuth & Permissions** and click **Install to Workspace** (or **Reinstall to Workspace**).
7. Copy the **Bot User OAuth Token** (starts with `xoxb-...`).
8. Invite the bot to any channel you want it to interact with:
   ```text
   /invite @px0-bot
   ```

### How to configure in px0
- **During `px0 init`:** When asked `Connect Slack as messaging tool? [y/N]`, type `y` and paste your `xoxb-...` token.
- **Manually:** Add it to your credentials file (`~/.px0/.state/credentials.toml`):
  ```toml
  [slack]
  token = "xoxb-..."
  ```
  Or export the environment variable:
  ```shell
  export SLACK_BOT_TOKEN="xoxb-..."
  ```
