# Contra project case study

## Facebook Page Reaction Abuse Monitoring and Moderation Automation

**Role:** Automation Architect, Developer and Operations Owner

> I identified the operational problem, designed the monitoring and moderation logic, built the automation and Facebook integration, configured its execution, deployed it, and used it to protect Pages I was responsible for.

**Summary:** I built a scheduled workflow that discovers Page objects through Graph, reads Angry/Haha reaction-browser activity through authenticated Playwright, and can submit a Page-level block under a verified originating Page identity.

## The abuse pattern

Facebook Pages I managed were targeted by coordinated accounts adding Angry and Haha reactions to posts and comments. The activity could make genuine Page content appear rejected or mocked, while manual monitoring across every content item and account was slow and inconsistent.

## The automation I built

I built a scheduled Python system that uses Graph to discover live Page posts, optional comments, and optional ratings. Current Meta documentation does not support enumeration of other users' reactions through Graph for this workflow, so authenticated Playwright reads bounded reaction-browser pages, requires configured `ANGRY`/`HAHA` label and icon-source pairs, and accepts validated numeric profile links. Atomic JSON state deduplicates Page/account work.

Detection-only still performs those browser reads, but no moderation mutation. When I deliberately invoke the apply path, Playwright switches to the Page that originated the incident, verifies that identity, and then attempts the Page-level block. If identity verification fails, the action stops. Optional Telegram notifications report activity without controlling the core workflow.

Page ratings are handled separately: configured Arabic keyword matches create alerts only and do not create account-block actions.

## Architecture

```text
Scheduler
  -> Facebook Graph: posts, comments, optional ratings
  -> authenticated Playwright reaction-browser scan
  -> configured label/icon and numeric-profile rules
  -> atomic JSON account/action deduplication
  -> detection-only state or explicit apply
  -> verified originating Page identity
  -> Playwright moderation action
  -> state record + optional Telegram alert
```

## Operational indicators

In my recorded deployment, I configured two Page pollers on eight-second intervals. My historical runtime queues contain 28 unique post URL strings and 210 unique profile URL strings. The runtime log contains 254 UI confirmation-click markers, 102 block-menu-not-found markers, and 119 completed-batch markers from 2025-05-14 through 2025-05-29.

Those are configuration values and derived runtime-record counts. A click marker is not a provider-confirmed block, and a completed batch does not prove that every action succeeded. Provider-confirmed blocks and current deployment status are unavailable.

## Public demonstration

This portfolio version presents the implemented monitoring, classification, deduplication, explicit apply, and action flow with placeholder configuration and synthetic identifiers. It contains no original tokens, cookies, Page or account identifiers, private URLs, state, or operational logs. Graph permissions plus the mbasic route, labels, icon-source markers, pagination, selectors, and comment compatibility require authorized live validation whenever the platform changes.

## Services this demonstrates

- Business-process automation
- Social monitoring automation
- Rule-based detection workflows
- API and browser integration
- Stateful operational tooling

## Stack

Python, Facebook Graph API, Playwright with Firefox, atomic JSON state, optional Telegram Bot API, and POSIX scheduling/locking.

## Visual order

1. Project cover
2. Monitoring architecture
3. Detection and pending-target decision flow
4. Originating Page action sequence
5. Historical operating indicators

## Short CTA

If you need a focused monitoring or workflow automation, I can map the signal, decision boundary, integrations, and operating constraints before building the smallest reliable version.

## Links

- Repository: `[REPOSITORY_URL]`
- Demo: `[DEMO_URL]`
- Contact: `[CONTACT_URL]`
