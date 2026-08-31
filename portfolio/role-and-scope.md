# Role and scope

## My role

**Automation Architect, Developer and Operations Owner**

> I identified the operational problem, designed the monitoring and moderation logic, built the automation and Facebook integration, configured its execution, deployed it, and used it to protect Pages I was responsible for.

## What I owned

- I identified coordinated Angry/Haha reaction abuse as an operational Page-management problem.
- I designed the monitoring, classification, duplicate-protection, and moderation flow.
- I built the Facebook Graph integration for Page post/comment discovery and rating alerts.
- I built the authenticated Playwright reaction-browser collector for configured Angry/Haha label/icon pairs and numeric profile links.
- I implemented the Page-level browser moderation path.
- I configured credentials and scheduled execution in the private operating environment.
- I deployed and operated the system on Pages for which I was responsible.
- I monitored its behavior and maintained it as platform behavior changed.
- I prepared this public demonstration without publishing private Page data or credentials.

## Functional scope

The system discovers live Page content through Graph, reads configured `ANGRY` and `HAHA` activity through a bounded authenticated Playwright reaction-browser scan, and deduplicates matching accounts and actions in atomic JSON state. Monitoring uses read-only browser access; the Page-level mutation remains behind explicit `--apply` mode. When an action is applied, Playwright must verify the originating Page identity before attempting it. An identity-switch failure stops the action.

Page-rating keyword matches are notification events only. Optional Telegram messages report operational events but are not required for monitoring, detection, deduplication, or action state.

Current Meta documentation does not support enumeration of other users' reactions through Graph for this workflow. The mbasic route, visible labels, icon-source markers, pagination text, selectors, and comment-object compatibility therefore require authorized live validation.

## Public demonstration boundary

The repository demonstrates my implemented workflow with placeholder configuration and synthetic identifiers. It does not include original access tokens, cookies, Page/profile/post identifiers, private URLs, or operational logs. It does not claim that the original deployment is currently active or turn local UI markers into provider-confirmed moderation results.

No license is declared in the repository.
