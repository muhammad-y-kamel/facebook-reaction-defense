# Facebook Page Reaction Abuse Monitoring and Moderation Automation

**Short name:** Angry/Haha Reaction Abuse Defense for Facebook Pages

**Role:** Automation Architect, Developer and Operations Owner

**Status:** Public demonstration of a system I built, deployed, and operated; I do not claim that the original deployment is currently active.

> I identified the operational problem, designed the monitoring and moderation logic, built the automation and Facebook integration, configured its execution, deployed it, and used it to protect Pages I was responsible for.

## The problem I addressed

Facebook Pages I managed were targeted by accounts that added coordinated Angry and Haha reactions to posts and comments. The pattern could distort how genuine customers perceived the content, while manually checking every post, comment, reaction, and account was too slow and easy to repeat inconsistently.

I built a monitoring and moderation automation to detect and respond to that reaction abuse. My goal was a continuous operational flow that could find relevant accounts, avoid acting on the same account repeatedly, keep the acting Page identity correct, and record enough state to resume safely.

## What I built

The system runs the following workflow:

```text
Scheduled execution
  -> discover Page posts, comments, and optional ratings through Graph
  -> read each object's authenticated Facebook reaction browser
  -> match configured ANGRY/HAHA label and icon-source pairs plus numeric profile links
  -> deduplicate accounts and planned actions in atomic JSON state
  -> queue a Page-level moderation action
  -> require explicit --apply mode
  -> switch to the originating Page identity in Playwright
  -> submit the Page-level block or stop closed
  -> record status and optionally notify through Telegram
```

The default mode is detection-only. It performs bounded authenticated browser reads and local state updates, but no moderation mutation. A moderation action is not attempted until I use the explicit apply path. During an apply run, the browser must confirm the originating Page identity before continuing. If the identity switch cannot be verified, the action stops instead of continuing under an uncertain Page identity.

## Monitoring and decision logic

I made the reaction types configurable, with `ANGRY` and `HAHA` as the supported abuse signals. Graph discovers the Page posts, optional comments, and optional ratings. It does not enumerate other users' reactions. Playwright opens the authenticated reaction-browser route for each discovered object, requires the configured visible label and icon-source marker, and accepts only validated numeric profile links.

For each matching account, the system creates or reuses a local account record and checks whether the same Page-scoped action has already been queued or submitted. A strict versioned JSON document provides the durable uniqueness boundary. A POSIX lock serializes access, and atomic replacement prevents a partial state document from being published.

Page ratings follow a separate path. Configured Arabic keyword matches can trigger an alert, but ratings do not create an account-block action. This keeps a content alert distinct from an account-level moderation decision.

## Moderation path

The action runner uses Playwright because the Page-level block is performed through the Facebook Page interface. Before touching the control, it selects the Page that originated the incident and verifies that identity. Only then does it navigate the account-level UI and attempt the block.

This boundary is intentionally explicit:

- detection performs authenticated reads but no moderation mutation;
- apply requires the deliberate `--apply` mode;
- an account/action pair is checked against local state;
- an unverified Page-identity switch stops the action;
- the result or failure state is recorded without exposing credentials;
- Telegram notification is optional, not required for core operation.

## Architecture

| Component | Responsibility |
|---|---|
| Scheduler / command entrypoint | Starts one monitoring cycle or the explicit action path |
| Facebook Graph integration | Discovers Page posts, optional comments, and optional ratings |
| Playwright reaction collector | Reads bounded reaction-browser pages and validates configured label/icon pairs plus numeric profiles |
| Detection rules | Selects configured Angry/Haha activity and rating-keyword alerts |
| Atomic JSON state | Deduplicates accounts and Page-scoped actions and records status |
| Playwright moderation runner | Switches to the originating Page identity and submits the Page-level block only in apply mode |
| Optional Telegram integration | Sends operational alerts without controlling the workflow |

Page tokens and notification credentials come from environment configuration. The public repository contains synthetic identifiers and examples only; it does not include the original tokens, browser session material, Page IDs, account IDs, URLs, or operational logs.

## Reliability and failure handling

I bound every Graph edge and divide its cycle request ceiling across configured Pages. I separately divide `MAX_REACTION_BROWSER_PAGES_PER_CYCLE` across Pages and cap unique actors per object. Transient Graph failures receive bounded retries. Fixed-order collection can defer later content when earlier objects consume a ceiling. `MAX_MODERATION_ACTIONS_PER_RUN` limits one apply pass, while one POSIX lock prevents conflicting state mutations.

Pre-confirmation browser failures remain `failed` and return to pending only through the explicit retry command. Interrupted `applying` records and ambiguous `uncertain` outcomes require Page-side reconciliation before I mark them submitted or requeue them. I do not claim cross-system exactly-once execution.

## Security and private data

I supply Page and Telegram credentials through private environment configuration. Graph credentials travel in bearer headers. Browser storage, JSON state, lock files, logs, and backups remain outside source control with restricted permissions. Third-party JSON, cursors, identifiers, URLs, labels, and UI state are validated at their boundaries. Before every target action, Playwright revalidates the acting Page and fails closed if the Page or numeric target URL cannot be confirmed.

## Technology stack

Python 3.11+, Python standard library HTTP/JSON/file handling, Facebook Graph API, Playwright with Firefox, optional Telegram Bot API notifications, and POSIX scheduling/locking.

## Historical operational indicators

My historical operating records provide useful scale indicators, but they are not provider-side proof of outcomes.

| Classification | Indicator | Value | Meaning |
|---|---|---:|---|
| Verified | Page pollers started by my historical launcher | 2 | Two independent Page monitoring processes were configured |
| Verified | Polling interval in those pollers | 8 seconds | Configured sleep between monitoring cycles |
| Derived | Unique queued post URLs | 28 | Unique URL strings in my historical runtime queue |
| Derived | Unique queued profile URL strings | 210 | Unique profile URL strings counted in the historical queue |
| Derived | UI confirmation-click log markers | 254 | Local markers written after a confirmation click; not confirmed blocks |
| Derived | Block-menu-not-found markers | 102 | Local markers for one UI failure condition |
| Derived | Completed-batch markers | 119 | Runs that reached their local final marker, not proof every action succeeded |
| Derived | Parsed log range | 2025-05-14 to 2025-05-29 | Earliest and latest timestamps in my historical runtime log |

The number of provider-confirmed blocks, accounts ultimately affected, posts or comments checked, detection accuracy, response-time improvement, and business impact are unavailable. I do not infer them from click or completion messages.

## Operational choices

- **Duplicate protection:** durable account/action keys prevent repeated local work across polling cycles.
- **Controlled action:** monitoring remains useful without enabling browser-side moderation.
- **Correct identity:** the originating Page is part of the action boundary, and uncertainty fails closed.
- **Small dependency surface:** the implementation uses standard-library JSON state plus Graph, Playwright, and optional Telegram without adding a service layer that this operator workflow does not need.
- **Private configuration:** credentials and browser state stay outside version control.

## Current constraints

Current Meta documentation does not support other-user reaction enumeration through Graph for this workflow. The mbasic reaction-browser route, visible labels, icon-source markers, pagination text, selectors, numeric profile links, and comment-object compatibility require authorized live validation. Graph fields, permissions, versions, and Page access rules can also change. This public repository does not establish current live compatibility.

The public demo is configured with placeholders and presented through synthetic visuals. It demonstrates the implemented monitoring, detection, deduplication, confirmation, and state flow without claiming a current live deployment or a provider-confirmed moderation count.

## Links

- Repository: `[REPOSITORY_URL]`
- Demo: `[DEMO_URL]`
- Contact: `[CONTACT_URL]`
