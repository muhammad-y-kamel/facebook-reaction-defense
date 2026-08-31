# Facebook Page Reaction Abuse Monitoring and Moderation Automation

An automation system that discovers configured Facebook Page posts and comments, reads their Angry/Haha reaction browsers, deduplicates matching accounts, and can submit an authorized Page-level moderation action.

## The problem

Facebook Pages I worked on were targeted by coordinated accounts that repeatedly added Angry and Haha reactions to posts and comments. The activity distorted the public appearance of the Pages, weakened customer trust, and was too repetitive to handle reliably by checking every surface manually.

I built this system to turn that workload into a repeatable monitoring and moderation flow.

## What the system does

The Facebook Graph API discovers Page posts, optional comments, and optional Page ratings/reviews. It does not enumerate other users' reactions. An authenticated, bounded Playwright scan opens Facebook's reaction-browser UI for each discovered object and identifies numeric profile links only when a visible label and its configured reaction-icon source marker both match.

Each matching Page/account signal is kept once in a private JSON state file. State updates are protected by a POSIX file lock and written through atomic replacement. Detection-only is the default: it reads the authenticated reaction browser and records local state, but it does not change Facebook. Explicit `--apply` additionally enables the Page-scoped block path.

Page ratings/reviews follow a separate path. Configured Arabic keywords may trigger an alert, but ratings/reviews never create an account-moderation target.

## Main capabilities

- Discovers configured Page posts through the Graph API with bearer authentication.
- Optionally discovers comments and checks Page ratings/reviews.
- Uses a bounded, authenticated Playwright reaction-browser scan to identify numeric profile links.
- Maps configured UI labels and icon-source markers to `ANGRY` and `HAHA`.
- Deduplicates Page-scoped accounts in an atomic, mode-`0600` JSON state file.
- Keeps detection free of moderation mutations unless `run --apply` is explicit.
- Applies moderation through Playwright under the originating Page identity.
- Fails closed when Page identity or the numeric target cannot be confirmed.
- Sends optional Telegram summaries without making delivery an authorization signal.
- Supports one-shot execution for cron, systemd timers, or another scheduler.

## System flow

```text
Configured Facebook Pages
→ Graph discovery of posts, optional comments, and optional ratings
→ Bounded read-only Playwright reaction-browser scan
→ Angry/Haha label + icon-source matching and numeric account extraction
→ Page/account deduplication in atomic JSON state
→ Detection-only stop or explicit authorized moderation
→ Recorded state, private logs, and optional Telegram summary
```

Page ratings/reviews branch from Graph discovery to keyword alerts only.

## Architecture

`reaction_defense.py` is the single command-line entrypoint. It coordinates four boundaries:

1. Environment configuration defines Pages, Graph discovery, reaction-browser labels and bounds, private paths, moderation controls, and optional notifications.
2. The Graph API discovers posts, optional comments, and optional ratings/reviews; it is not used to enumerate other users' reactions.
3. Playwright reads the authenticated Facebook reaction browser during monitoring and performs Page UI moderation only when `--apply` is explicit.
4. A private JSON file stores deduplication keys and processing outcomes with `flock` serialization and atomic replacement.

See [docs/architecture.md](docs/architecture.md) for the component and trust-boundary view.

## Detection and moderation logic

For each configured Page, the system walks Graph discovery within `MAX_EDGE_PAGES` and the Page's share of `MAX_GRAPH_REQUESTS_PER_CYCLE`. It then scans each discovered post or comment through the Facebook reaction-browser UI, stopping at `MAX_REACTION_ACTORS_PER_OBJECT`. A reaction must match both its normalized visible label and configured icon-source marker; only numeric `profile.php?id=` links become targets.

Without `--apply`, the run ends after authenticated browser reads, detection, state persistence, logging, and optional notification. With `--apply`, a bounded set of pending targets enters the Page-scoped browser action path. The browser confirms the originating Page before attempting the block. Failed or ambiguous actions remain visible for deliberate reconciliation.

## Configuration

| Variable | Purpose |
|---|---|
| `META_GRAPH_VERSION` | Graph API version to use; verify current support before deployment |
| `META_PAGES_JSON` | JSON configuration for Pages and environment-supplied access tokens |
| `REACTION_TYPES` | Enabled reaction keys; defaults to `ANGRY,HAHA` |
| `MONITOR_COMMENTS` | Enable or disable comment discovery |
| `MONITOR_RATINGS` | Enable or disable Page ratings/reviews monitoring |
| `REVIEW_KEYWORDS` | Comma-separated Arabic terms for ratings/reviews alerts |
| `POLL_INTERVAL_SECONDS` | Delay between continuous polling cycles |
| `GRAPH_TIMEOUT_SECONDS` | Timeout for Graph API requests |
| `MAX_EDGE_PAGES` | Maximum pagination depth for each Graph or reaction-browser traversal |
| `MAX_GRAPH_REQUESTS_PER_CYCLE` | Graph request ceiling for one cycle, divided across Pages |
| `MAX_REACTION_BROWSER_PAGES_PER_CYCLE` | Total reaction-browser page ceiling for one cycle, divided across Pages |
| `MAX_REACTION_ACTORS_PER_OBJECT` | Maximum unique reaction accounts retained per post or comment |
| `MAX_MODERATION_ACTIONS_PER_RUN` | Maximum pending Page blocks selected in one apply pass |
| `DEFENSE_STATE_PATH` | Private JSON processing-state path; commands can override it with `--state` |
| `DEFENSE_LOG_PATH` | Private operational log path |
| `BROWSER_STORAGE_STATE` | Required for any `run`: private mode-`0600` Playwright JSON state, at most 5,000,000 bytes, with exactly `cookies` and `origins` arrays |
| `BROWSER_HEADLESS` | Run the browser headlessly or visibly |
| `FACEBOOK_REACTION_LABELS_JSON` | Exact mapping from enabled reaction keys to current visible UI labels |
| `FACEBOOK_REACTION_ICON_SRC_MARKERS_JSON` | Exact mapping from enabled reaction keys to verified substrings in their icon `src` values |
| `FACEBOOK_REACTION_MORE_TEXT` | Locale-specific text for loading more reaction accounts |
| `FACEBOOK_*_TEXT` | Locale-specific Page-switch and moderation UI text |
| `TELEGRAM_BOT_TOKEN` | Optional Telegram bot credential |
| `TELEGRAM_CHAT_IDS_JSON` | Optional JSON list of Telegram destinations |

The application reads exported environment variables directly. Keep live values out of `.env.example`, source control, screenshots, and logs.

## Installation and execution

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install firefox

python reaction_defense.py check-config
python reaction_defense.py run --once
python reaction_defense.py status
```

Every `run` requires valid private browser storage because detection reads Facebook's authenticated reaction-browser UI. `check-config` and state-inspection commands do not require the file. Runtime validation accepts only a regular mode-`0600` Playwright JSON file inside a private directory, validates its Facebook cookie/origin entries, and passes the validated in-memory object to the browser. Detection makes no moderation mutation. After validating permissions, browser access, locale text, icon markers, selectors, and Page identity on an authorized test Page, enable the action boundary explicitly:

```bash
python reaction_defense.py run --once --apply
```

Every state command accepts an explicit private state path:

```bash
python reaction_defense.py status --state /absolute/private/path/reaction-defense-state.json
python reaction_defense.py retry-failed --state /absolute/private/path/reaction-defense-state.json --confirm RETRY_FAILED_ACTIONS
python reaction_defense.py incomplete --state /absolute/private/path/reaction-defense-state.json
python reaction_defense.py incomplete --state /absolute/private/path/reaction-defense-state.json --show-identifiers --confirm SHOW_PRIVATE_IDENTIFIERS
python reaction_defense.py resolve-incomplete TARGET_REF requeue --state /absolute/private/path/reaction-defense-state.json --confirm RESOLVE_INCOMPLETE_ACTION
```

Use `submitted` instead of `requeue` only after confirming that the Page action occurred.

Detailed setup is in [docs/setup.md](docs/setup.md).

## Contributing

Fork the repository, create a focused branch, and open a pull request describing the behavior changed and how you verified it. Never include live credentials, browser storage, runtime state, logs, or private identifiers.

## Scheduling

The monitor supports one-shot execution so the operating environment controls scheduling. A detection-only cron entry can run it every five minutes:

```cron
*/5 * * * * cd /absolute/path/to/project && /absolute/path/to/project/.venv/bin/python reaction_defense.py run --once
```

Detection-only still opens the authenticated browser for read-only reaction collection. Add `--apply` only when unattended moderation is explicitly intended and validated. `POLL_INTERVAL_SECONDS` is used when running without `--once`.

## Error handling

Graph calls use fixed origins, bearer headers, timeouts, bounded pagination, response-size limits, and a divided per-cycle budget. Transient network failures, HTTP 429, and selected 5xx responses receive up to three total attempts. Playwright reaction collection is bounded by a cycle ceiling divided across Pages and an actor ceiling per object; it validates object URLs, label/icon-marker pairs, and numeric profile links. State mutations are serialized with `flock`; JSON is strictly parsed and atomically replaced so an interrupted write does not publish a partial document.

Each apply pass selects at most `MAX_MODERATION_ACTIONS_PER_RUN` pending targets. Page-switch failures stop safely. Pre-confirmation failures require explicit retry; interrupted or ambiguous outcomes require Page-side reconciliation. Telegram is optional and cannot authorize moderation.

## Security and privacy

Facebook tokens, browser storage state, Page/account/post/comment identifiers, Telegram credentials, JSON state, lock files, and operational logs are private deployment material. None belong in the public repository. The state and lock files are created with mode `0600`; their containing directory and backups should also be restricted.

Read [SECURITY.md](SECURITY.md) before connecting a live Page.

## Limitations

- Current Meta documentation does not provide this workflow with supported enumeration of other users' reactions through the Graph API; reaction-account discovery therefore uses Facebook's authenticated reaction-browser UI.
- The mbasic reaction-browser URL, visible labels, icon-source markers, pagination text, selectors, and comment-object compatibility require authorized live validation before deployment and after Facebook changes.
- Meta permissions, Page access behavior, and supported Graph API versions also require deployment-time validation.
- The target guard requires a numeric `profile.php?id=` URL. Other canonical profile forms fail closed until they can be verified safely.
- `MAX_EDGE_PAGES`, `MAX_GRAPH_REQUESTS_PER_CYCLE`, `MAX_REACTION_BROWSER_PAGES_PER_CYCLE`, and `MAX_REACTION_ACTORS_PER_OBJECT` intentionally bound discovery; a run does not claim exhaustive coverage beyond them.
- Provider-order traversal has no persisted cursor rotation, so sustained early-edge volume may defer later objects.
- `MAX_MODERATION_ACTIONS_PER_RUN` leaves excess pending targets for a later apply pass.
- Reaction-label matching is a deterministic signal, not proof that an account belongs to a coordinated campaign.
- This public repository contains no live credentials, private operational data, claim of current deployment, or provider-confirmed moderation count.

## My role

> I identified the operational problem, designed the monitoring and moderation logic, built the automation and Facebook integration, configured its execution, deployed it, and used it to protect Pages I was responsible for.

**Role:** Automation Architect, Developer and Operations Owner

## Project status

Open-source reference implementation of a system I deployed and operated. Current Meta permissions, mbasic reaction-browser compatibility, Facebook UI selectors, and live moderation behavior must be validated in an authorized environment before use.

## License

[MIT](LICENSE)
