# Project facts

## Identity

- **Project:** Facebook Page Reaction Abuse Monitoring and Moderation Automation
- **Short name:** Angry/Haha Reaction Abuse Defense for Facebook Pages
- **Category:** Facebook Page monitoring, reaction-abuse detection, moderation automation, and operational response
- **My role:** Automation Architect, Developer and Operations Owner
- **Public status:** Public demonstration of a system I built, deployed, and operated; no claim of a currently active deployment

> I identified the operational problem, designed the monitoring and moderation logic, built the automation and Facebook integration, configured its execution, deployed it, and used it to protect Pages I was responsible for.

## Implemented behavior

- I use the Graph API to discover live Facebook Page posts, optional comments, and optional ratings; I do not use it to enumerate other users' reactions.
- An authenticated, bounded Playwright scan reads the Facebook reaction browser and requires the configured visible label plus icon-source marker for `ANGRY` or `HAHA`.
- Only validated numeric profile links become account targets.
- Matching accounts enter a Page-scoped moderation workflow.
- Page ratings are checked for configured Arabic keywords and create alerts only; they do not create account-block actions.
- Strict atomic JSON state deduplicates account records and Page-scoped action records across polling cycles.
- Detection-only is the default operating boundary.
- Moderation requires the explicit apply path.
- Playwright performs read-only reaction collection during monitoring and the configured Page UI action only in explicit apply mode.
- The Page-identity switch must be verified; uncertainty stops the action.
- Telegram notifications are optional.
- The system records processing and action state locally.

## Trust boundaries

- Graph API responses and Facebook UI state are third-party controlled.
- Page tokens, Telegram credentials, and browser session state are environment-controlled secrets.
- Reaction and rating content is third-party input.
- Local JSON state derives from third-party account and content activity and remains untrusted when read back.
- The public repository uses synthetic identifiers and does not include original tokens, cookies, Page/account IDs, URLs, or logs.

## Historical indicators

- Verified: 2 Page pollers were configured in my historical launcher.
- Verified: both pollers used an 8-second polling interval.
- Derived: 28 unique post URL strings and 210 unique profile URL strings appeared in my historical runtime queues.
- Derived: my historical runtime log contains 254 confirmation-click markers, 102 menu-not-found markers, and 119 completed-batch markers between 2025-05-14 and 2025-05-29.
- A click marker is not a confirmed block, and a completed-batch marker is not proof every action succeeded.

## Current limits

- Graph API permissions, fields, versions, and access rules can change.
- Current Meta documentation does not support other-user reaction enumeration through Graph for this workflow.
- The mbasic reaction-browser route, labels, icon-source markers, pagination text, selectors, and comment-object compatibility require authorized live validation.
- Fixed-order, bounded collection may defer later content.
- Provider-confirmed moderation outcomes are unavailable from my historical operating records.
- No current live deployment is claimed.
- No public license is declared.
