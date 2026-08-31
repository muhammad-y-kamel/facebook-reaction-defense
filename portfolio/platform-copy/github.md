# GitHub publication copy

## Repository name options

- `facebook-reaction-abuse-defense` — recommended
- `facebook-page-reaction-moderation`
- `angry-haha-page-defense`

## Description

My Facebook Page automation for Graph object discovery, authenticated Angry/Haha reaction-browser scanning, atomic JSON deduplication, and explicit Playwright moderation.

## Topics

`python`, `playwright`, `json`, `facebook-graph-api`, `facebook-pages`, `workflow-automation`, `social-monitoring`, `reaction-monitoring`, `moderation-automation`, `rule-based-detection`

## README introduction

# Facebook Page Reaction Abuse Monitoring and Moderation Automation

I built this system to monitor and respond to Angry/Haha reaction abuse used in coordinated attacks against Facebook Pages. Graph discovers Page objects; authenticated Playwright reads their bounded reaction-browser pages and requires configured labels plus icon-source markers before accepting numeric profiles. Atomic JSON state prevents duplicate Page/account work. Detection makes browser reads but no moderation mutation, while explicit `--apply` enables Page-scoped blocking. Rating keywords alert only, and Telegram is optional.

**Role:** Automation Architect, Developer and Operations Owner

> I identified the operational problem, designed the monitoring and moderation logic, built the automation and Facebook integration, configured its execution, deployed it, and used it to protect Pages I was responsible for.

This repository is a public demonstration of the system. It does not contain original credentials, cookies, Page/account identifiers, private URLs, or operational logs, and it does not claim that the original deployment is currently active.

## Social preview

**Title:** Facebook Reaction Abuse Defense

**Subtitle:** Monitor → Detect → Deduplicate → Moderate → Log
**Asset:** `portfolio/assets/wide-cover-1600x900.png`

## Release description

### Public demonstration

- Graph discovery for Page posts, optional comments, and ratings
- Authenticated, bounded Playwright reaction-browser collection
- Configurable `ANGRY` and `HAHA` label/icon-source matching
- Rating-keyword alerts separated from account moderation
- Atomic JSON account and Page-scoped action deduplication
- Detection-only default with explicit `--apply` mode
- Playwright moderation under a verified originating Page identity
- Optional Telegram notifications
- Placeholder configuration and synthetic demonstration data

Current Meta documentation does not support other-user reaction enumeration through Graph for this workflow. Meta permissions plus the mbasic route, labels, icon-source markers, pagination, selectors, comment compatibility, and authorized browser session require live validation. No provider-confirmed moderation count or current deployment is claimed.

No public license is declared.

## Links

- Repository: `[REPOSITORY_URL]`
- Demo: `[DEMO_URL]`
