# Ureed portfolio copy — English

## Project title

Facebook Page Reaction Abuse Monitoring and Moderation Automation

## Role

Automation Architect, Developer and Operations Owner

## Summary

I built and operated a Python automation that uses Graph to discover Facebook Page posts, optional comments, and ratings. Authenticated Playwright reads bounded reaction-browser pages, requires configured Angry/Haha label/icon pairs, and accepts numeric profile links. Atomic JSON state deduplicates Page/account work. Detection makes browser reads but no moderation mutation; explicit `--apply` enables the fail-closed Page-level block path. Rating keywords alert only, and Telegram is optional. Current mbasic label/icon matchers, selectors, pagination, and comment compatibility require authorized live validation.

> I identified the operational problem, designed the monitoring and moderation logic, built the automation and Facebook integration, configured its execution, deployed it, and used it to protect Pages I was responsible for.

## Stack

Python, Facebook Graph API, Playwright, atomic JSON state, optional Telegram

## Five skills

- Python automation
- API integration
- Browser automation
- Rule-based detection
- Operational workflow design

## Verified outcome

My historical operating configuration ran two Page pollers at eight-second intervals. Private runtime records contain 28 unique queued post URL strings and 210 unique queued profile URL strings; provider-confirmed block totals are unavailable.

## Public demonstration boundary

The repository uses placeholder configuration and synthetic identifiers. Original tokens, browser sessions, Page/account IDs, private URLs, and operational logs are not included. I claim neither a current deployment nor provider-confirmed outcomes without authorized live verification in that environment.

## Links

- Repository: `[REPOSITORY_URL]`
- Demo: `[DEMO_URL]`
- Contact: `[CONTACT_URL]`
