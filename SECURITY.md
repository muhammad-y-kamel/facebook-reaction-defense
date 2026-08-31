# Security policy

## Reporting a vulnerability

Report vulnerabilities through a private GitHub security advisory. Do not include Facebook or Telegram tokens, browser storage state, Page/account/content identifiers, private URLs, JSON state, logs, screenshots containing operational data, or other personal data in a public issue.

## Protected material

Keep these deployment secrets and operational artifacts outside source control:

- `META_PAGES_JSON`, because each Page object contains an access token.
- `BROWSER_STORAGE_STATE`, because every `run` uses authenticated browser state that can contain session cookies. Runtime accepts only a regular mode-`0600` Playwright JSON file inside a private directory, validates its bounded Facebook cookie/origin structure, and gives the validated in-memory object to Playwright.
- `TELEGRAM_BOT_TOKEN` and private Telegram destinations.
- Live `reaction-defense-state*.json` files, their lock files, backups, and operational logs.
- Real Page, account, post, comment, rating/review, and profile identifiers or URLs.

Supply secrets through the process environment or a deployment secret manager. Use least privilege, restrict the browser account to intended Pages, and replace credentials after exposure or an operator-access change.

## Trust boundaries

- Environment configuration is operator controlled but strictly parsed because malformed values can select the wrong resource or weaken bounds.
- Graph responses and pagination cursors are third-party controlled. Graph discovers Page objects and optional ratings; it is not trusted or used to enumerate other users' reactions.
- Facebook reaction-browser content, profile links, labels, pagination, and moderation controls are third-party controlled.
- Telegram responses are third-party controlled and delivery is not an authorization signal.
- Local JSON fields derive from external Page activity and remain untrusted when read back.

## Operational safeguards

- `run` performs authenticated browser reads but no moderation mutation unless the operator explicitly supplies `--apply`.
- Graph credentials use bearer headers rather than URL query strings.
- Fixed origins, timeouts, response-size limits, `MAX_EDGE_PAGES`, and per-Page request shares bound Graph access.
- `MAX_REACTION_ACTORS_PER_OBJECT` bounds unique reaction accounts retained from each post or comment.
- `MAX_MODERATION_ACTIONS_PER_RUN` bounds each apply pass; excess targets remain pending.
- Reaction labels and icon-source markers must exactly cover the enabled reaction keys; only rows matching both values and a validated numeric profile link become targets.
- Every moderation action remains associated with its originating Page. Identity or target uncertainty fails closed.
- Ratings/reviews keyword matches may alert but never create moderation targets.
- State is strictly decoded, versioned, serialized under a nonblocking POSIX lock, and committed by atomic file replacement. State and lock files use mode `0600`.
- Failed-action retry and incomplete-action reconciliation require their exact confirmation values; ambiguous outcomes are not retried automatically.

## Logging and notifications

Logs and Telegram summaries must not expose access tokens, cookies, authorization headers, raw browser state, raw provider responses, or unnecessary identifiers. Retain private operational material only as long as required.

Telegram is optional. A notification error cannot bypass identity checks, enable apply mode, or erase a recorded outcome.

## Safe live-use boundary

Current Meta documentation does not support enumerating other users' reactions through the Graph API for this workflow. The authenticated Playwright collector therefore depends on Facebook's mbasic reaction-browser route and visible UI state. Before any live deployment, validate Graph permissions and version plus the mbasic URL, reaction labels, icon-source markers, pagination text, selectors, comment-object compatibility, Page-switch flow, and moderation controls on an authorized test Page.

Use only Pages and accounts you are authorized to administer. Validate changes against a dedicated non-production Page before live use.
