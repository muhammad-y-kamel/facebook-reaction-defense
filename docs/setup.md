# Setup

## Requirements

- Python 3.11 or newer
- A POSIX-compatible host because state coordination uses `flock`
- Playwright with Firefox for reaction monitoring and optional moderation
- Authorized access to every configured Facebook Page
- Current Page access tokens for Graph content discovery
- A private Playwright storage-state file for every monitoring run

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install firefox
```

## Obtain private credentials

Facebook and Telegram credentials do not come from GitHub. Create a Meta app under the account that is authorized to manage the Pages, obtain a User access token with the current Page-read permissions required by the configured Graph fields, then obtain the corresponding Page access token through the official [Meta access-token flow](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/). Confirm the current permission names and any App Review or business-verification requirements in Meta's [Permissions Reference](https://developers.facebook.com/docs/permissions/).

Telegram is optional. Create or manage the bot through the official [@BotFather flow](https://core.telegram.org/bots/features#botfather), keep its token private, and configure only the intended chat IDs.

## Configure Pages

```bash
export META_GRAPH_VERSION='vXX.X'
export META_PAGES_JSON='[{"id":"1234567890","name":"Example Page","url":"https://www.facebook.com/example.page","access_token":"replace-me"}]'
```

Replace placeholders at deployment time. Keep the live JSON in a secret manager or restricted environment file.

## Configure monitoring and state

```bash
export REACTION_TYPES='ANGRY,HAHA'
export MONITOR_COMMENTS='true'
export MONITOR_RATINGS='true'
export REVIEW_KEYWORDS='نصاب,نصابين,لا انصح,حرامي,حرامية,نصب'
export POLL_INTERVAL_SECONDS='30'
export GRAPH_TIMEOUT_SECONDS='20'
export MAX_EDGE_PAGES='10'
export MAX_GRAPH_REQUESTS_PER_CYCLE='500'
export MAX_REACTION_BROWSER_PAGES_PER_CYCLE='100'
export MAX_REACTION_ACTORS_PER_OBJECT='500'
export MAX_MODERATION_ACTIONS_PER_RUN='25'
export DEFENSE_STATE_PATH='/absolute/private/path/reaction-defense-state.json'
export DEFENSE_LOG_PATH='/absolute/private/path/reaction-defense.log'
```

Graph requests discover objects only. The reaction-browser page ceiling is a separate total divided across configured Pages. Both traversals are fixed-order and bounded, so later content may be deferred. `check-config` validates booleans, numbers, paths, Page objects, reaction keys, and JSON mappings.

## Prepare authenticated browser monitoring

Create storage state only from an authorized operator session, outside the repository:

```bash
install -d -m 700 /absolute/private/path
python -m playwright codegen \
  --save-storage=/absolute/private/path/facebook-storage-state.json \
  https://www.facebook.com/
chmod 600 /absolute/private/path/facebook-storage-state.json
export BROWSER_STORAGE_STATE='/absolute/private/path/facebook-storage-state.json'
export BROWSER_HEADLESS='true'
export FACEBOOK_REACTION_LABELS_JSON='{"ANGRY":"Angry","HAHA":"Haha"}'
export FACEBOOK_REACTION_ICON_SRC_MARKERS_JSON='{"ANGRY":"replace-with-angry-icon-marker","HAHA":"replace-with-haha-icon-marker"}'
export FACEBOOK_REACTION_MORE_TEXT='See More'
```

Complete login interactively and close the codegen browser. Replace the examples with the exact labels and stable substrings from each reaction icon's `src` value in the authorized current DOM. Also configure the Page-switch and moderation `FACEBOOK_*_TEXT` values in [.env.example](../.env.example).

The storage-state file is required for every `run` because reaction actors are read from the authenticated Facebook UI. Runtime validation requires a regular mode-`0600` Playwright JSON file no larger than 5,000,000 bytes inside a mode-`0700` directory; it validates bounded Facebook cookie/origin entries before passing the in-memory object to Playwright. `check-config` and state-inspection commands do not require the file. Detection-only makes browser reads but performs no moderation mutation.

## Optional Telegram summaries

```bash
export TELEGRAM_BOT_TOKEN='replace-me'
export TELEGRAM_CHAT_IDS_JSON='["123456789"]'
```

Leave both unset to disable Telegram.

## Validate and run

```bash
python reaction_defense.py check-config
python reaction_defense.py run --once
python reaction_defense.py status --state /absolute/private/path/reaction-defense-state.json
```

After authorized live validation of Graph permissions, mbasic reaction-browser behavior, labels, icon-source markers, selectors, comment objects, Page switching, and block controls, explicitly enable moderation if intended:

```bash
python reaction_defense.py run --once --apply
```

The state file and sidecar lock use mode `0600`. Keep their directory, browser storage, log, environment file, and backups restricted.
