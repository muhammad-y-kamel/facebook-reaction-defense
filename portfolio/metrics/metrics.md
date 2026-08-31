# Project metrics

These metrics describe my historical operation. I use **Verified** for values stated directly by my operating configuration, **Derived** for deterministic counts from my private runtime records, and **Unavailable** when those records cannot support a claim.

| Classification | Metric | Value | Definition and limit |
|---|---|---:|---|
| Verified | Page pollers in the historical launcher | 2 | Two Page-monitoring processes were configured to start |
| Verified | Polling interval | 8 seconds | The configured sleep between cycles in both historical pollers |
| Derived | Unique queued post URL strings | 28 | Distinct strings in the historical post queue; not a count of all posts checked |
| Derived | Unique queued profile URL strings | 210 | Distinct strings in the historical profile queue; not a count of confirmed moderation outcomes |
| Derived | UI confirmation-click log markers | 254 | Messages written after the automation clicked a confirmation control; not provider-confirmed blocks |
| Derived | Block-menu-not-found markers | 102 | Messages for one observed UI-control failure condition |
| Derived | Completed-batch markers | 119 | Messages indicating a local batch reached its final marker; not proof every action succeeded |
| Derived | Historical log date range | 2025-05-14 to 2025-05-29 | Earliest and latest parsed timestamps in my historical runtime log |

## Unavailable metrics

- Provider-confirmed successful blocks
- Unique accounts ultimately moderated
- Total posts checked
- Total comments checked
- Total reaction records processed
- Detection precision or recall
- Response-time reduction
- Moderation hours saved
- Current uptime or deployment status
- Business or reputation impact

I do not convert click markers, profile URL strings, or completed-batch markers into external outcomes.
