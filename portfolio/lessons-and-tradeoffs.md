# Lessons and tradeoffs

## 1. The acting Page is part of the authorization boundary

I designed each moderation action around its originating Page. The Playwright path must switch to and verify that Page identity before continuing. If the switch is uncertain, the action stops.

**Tradeoff:** this adds a browser step and depends on the current Facebook UI, but it prevents an action from continuing under the wrong Page identity.

## 2. Detection and action should be separable

The system can monitor, classify, deduplicate, and record incidents without changing Page state. I kept moderation behind an explicit apply path.

**Tradeoff:** an operator must make a deliberate execution decision. That is useful when the external action is difficult to reverse or the platform UI has changed.

## 3. One strict state document is enough for this operator workflow

I keep account and Page-scoped action keys in a versioned JSON document. A POSIX lock serializes access, and atomic replacement avoids publishing partial writes.

**Tradeoff:** this fits one POSIX-host operator workflow. A shared service would become relevant only after a verified multi-host or multi-tenant requirement.

## 4. Reaction and rating signals need different outcomes

I use configured `ANGRY` and `HAHA` reactions for the account-level workflow. Arabic keyword matches in Page ratings generate alerts only.

**Tradeoff:** deterministic rules are transparent and controllable, but they do not infer intent or context. They need operational tuning when patterns change.

## 5. Browser automation is useful but inherently coupled to the UI

Playwright made the implemented Page-level moderation action possible, including Page-identity selection. It also inherits the platform interface's selectors, language, timing, permissions, and session behavior.

**Tradeoff:** the UI path needs maintenance after Facebook changes. A run must stop cleanly when a required identity or control cannot be verified.

## 6. Notifications should not control the workflow

Telegram is optional. Monitoring and local state continue to have a clear outcome even when notification delivery is unavailable.

**Tradeoff:** operators need another way to inspect state when Telegram is disabled or unreachable.

## 7. Operational logs are indicators, not provider receipts

Historical click and completed-batch markers show which local steps the automation reached. I do not present them as proof that Facebook confirmed a final block.

**Tradeoff:** this keeps public claims accurate, while provider-confirmed outcomes would require a supported response or a separately authorized verification step.

## 8. Public examples should present the workflow, not private identities

The public demonstration uses synthetic identifiers and environment-based configuration. Original tokens, session material, Page/account IDs, URLs, and logs remain outside it.

**Tradeoff:** the public demo cannot prove current Page permissions or UI compatibility. Those checks belong in an authorized deployment environment.

## 9. Discovery follows two external boundaries

I use Graph for Page objects and authenticated Playwright for other users' reaction entries. Current Meta documentation does not support the latter enumeration through Graph for this workflow.

**Tradeoff:** the mbasic reaction-browser route, labels, pagination text, selectors, and comment-object compatibility require authorized live checks. Bounded fixed-order scans may defer later content.
