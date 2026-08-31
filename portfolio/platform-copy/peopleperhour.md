# PeoplePerHour portfolio copy

## Direct title

Facebook Page Reaction Abuse Monitoring and Moderation Automation

## Role

Automation Architect, Developer and Operations Owner

> I identified the operational problem, designed the monitoring and moderation logic, built the automation and Facebook integration, configured its execution, deployed it, and used it to protect Pages I was responsible for.

## 100-word version

I built and operated a Python system that uses Graph to discover Facebook Page posts, comments, and ratings, then Playwright to read authenticated reaction-browser pages for configured Angry/Haha label/icon pairs. Numeric profiles are deduplicated in atomic JSON state. Detection-only performs browser reads but no moderation mutation; explicit `--apply` enables the Page-scoped block path. Arabic rating keywords alert only, and Telegram is optional. Collector has bounded Page and actor budgets. This demonstration excludes credentials, sessions, identifiers, private URLs, and logs. Current mbasic label/icon matchers, selectors, pagination, and comment compatibility require authorized live validation; no active deployment or provider-confirmed outcome is claimed.

## 250-word version

I created this automation after Facebook Pages I managed were targeted with coordinated Angry and Haha reactions on posts and comments. Manual monitoring was slow and made it difficult to identify relevant accounts, avoid repeated work, and respond consistently.

The system uses Facebook Graph to discover Page posts, optional comments, and optional ratings. It does not use Graph to enumerate other users' reactions. Instead, authenticated Playwright visits each discovered object's reaction-browser route, requires current visible label/icon pairs configured for `ANGRY` and `HAHA`, and accepts only validated numeric profile links. A strict versioned JSON document keeps Page/account observations and action status across cycles. A POSIX lock serializes access, and atomic replacement prevents partial state writes.

Detection-only still performs authenticated browser reads, but it makes no moderation mutation. Explicit `--apply` selects a bounded set of pending targets. Playwright confirms the originating Page before attempting a Page-level block and fails closed when identity or target validation is uncertain. Arabic keyword matches in Page ratings alert only; Telegram notification is optional.

I designed, built, deployed, and operated the original system. This public repository uses placeholders and synthetic identifiers and excludes tokens, cookies, private URLs, and operational logs. Graph requests, reaction-browser pages, actors per object, and apply batches all have explicit ceilings. Current Meta documentation does not support this reaction enumeration through Graph. The mbasic route, label/icon matchers, pagination text, selectors, and comment-object compatibility require authorized live validation. I claim neither current deployment nor provider-confirmed outcomes. The workflow stays bounded and inspectable for deliberate operation.

## Skills

Python, Playwright, JSON state, Facebook Graph API, workflow automation

## Visual order

1. Project cover
2. Live monitoring architecture
3. Detection and duplicate protection
4. Page-identity action flow
5. Project indicators

## Verified outcome

My historical operating configuration ran two Page pollers at eight-second intervals. Private runtime records contain 28 unique queued post URL strings and 210 unique queued profile URL strings. Provider-confirmed block totals are unavailable.

## Links

- Repository: `[REPOSITORY_URL]`
- Demo: `[DEMO_URL]`
