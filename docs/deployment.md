# Deployment

The application can run on a private workstation or a small POSIX service host. The smallest deployment is a Python environment, a mode-`0700` runtime directory, injected secrets, and a scheduler invoking `run --once`.

## Preflight

Before connecting a live Page:

1. Confirm the supported Graph API version and permissions needed to discover the configured Page surfaces.
2. Verify every Page ID, URL, name, and access token in `META_PAGES_JSON`.
3. Create private Playwright storage state from an authorized Facebook operator session; every `run` requires it even without `--apply`. It must be a regular mode-`0600` Playwright JSON file no larger than 5,000,000 bytes inside a mode-`0700` directory.
4. Validate the mbasic reaction-browser route, numeric profile links, reaction labels, icon-source markers, more-results text, selectors, and comment-object compatibility against the authorized current UI.
5. Verify Page-switch and moderation controls on a dedicated non-production Page before enabling `--apply`.
6. Set Graph, reaction-browser, actor, and apply ceilings for the host's capacity and intended scope.
7. Keep state, lock, log, secrets, and browser storage outside the public checkout where practical.
8. Run Python syntax compilation before deployment.

## Private runtime files

```bash
install -d -m 700 /absolute/private/path/reaction-defense
umask 077
```

Store `reaction-defense-state.json`, its sidecar lock, the log, browser storage, and any environment file there. Do not copy them into a public repository or build artifact.

## Configuration

Supply configuration through the process environment or a secret manager. `META_PAGES_JSON` has this exact shape:

```json
[
  {
    "id": "1234567890",
    "name": "Example Page",
    "url": "https://www.facebook.com/example.page",
    "access_token": "replace-me"
  }
]
```

The example is synthetic. Validate the complete environment before scheduling:

```bash
python reaction_defense.py check-config
```

## Start modes

Detection-only one-shot run; this performs authenticated read-only browser collection:

```bash
python reaction_defense.py run --once
```

Authorized one-shot run with Page-scoped moderation enabled:

```bash
python reaction_defense.py run --once --apply
```

Continuous monitoring uses `POLL_INTERVAL_SECONDS`:

```bash
python reaction_defense.py run
```

Add `--apply` to a continuous or scheduled process only when unattended moderation is an intentional, validated operational decision.

## Minimal scheduling

```cron
*/5 * * * * cd /absolute/path/to/project && /absolute/path/to/project/.venv/bin/python reaction_defense.py run --once
```

Use absolute paths and the host's secret-management mechanism. Never put tokens in the crontab.

## Operations

All state commands accept `--state`; otherwise they use `DEFENSE_STATE_PATH`.

```bash
python reaction_defense.py status --state /absolute/private/path/reaction-defense-state.json
python reaction_defense.py retry-failed --state /absolute/private/path/reaction-defense-state.json --confirm RETRY_FAILED_ACTIONS
python reaction_defense.py incomplete --state /absolute/private/path/reaction-defense-state.json
python reaction_defense.py incomplete --state /absolute/private/path/reaction-defense-state.json --show-identifiers --confirm SHOW_PRIVATE_IDENTIFIERS
python reaction_defense.py resolve-incomplete TARGET_REF submitted --state /absolute/private/path/reaction-defense-state.json --confirm RESOLVE_INCOMPLETE_ACTION
```

Use `requeue` only after verifying that the Facebook action did not occur. Keep backups restricted. Because a UI action and a JSON update are separate systems, inspect both sides after interruption before resolving or retrying.

## Deployment boundary

Python syntax compilation verifies local parseability only. Current Meta permissions plus mbasic reaction-browser and moderation compatibility remain unverified until checked in an authorized live environment. This repository does not claim a currently active deployment.
