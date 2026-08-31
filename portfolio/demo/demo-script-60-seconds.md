# 60-second silent demo script

I use this sequence to present the project in my own voice. The video contains synthetic visuals only and makes no live request.

| Time | Visual | Caption |
|---:|---|---|
| 0:00-0:07.5 | Wide cover and abstract signal-defense hero | I built a defense workflow for coordinated Angry and Haha reaction abuse on Facebook Pages. |
| 0:07.5-0:15 | Sequence diagram, ratings-first step | I check optional Page ratings first through Graph. New Arabic keyword matches can alert, but never enter blocking. |
| 0:15-0:22.5 | Architecture diagram, discovery and browser scan | I use Graph only to discover post and comment IDs, then authenticated Playwright scans bounded reaction-browser pages. |
| 0:22.5-0:30 | Decision flow, browser and state boundary | I require an Angry/Haha label plus its icon-source marker before accepting a numeric profile, then deduplicate it in atomic JSON state. |
| 0:30-0:37.5 | Decision flow, detection-only and pending selection | Detection-only makes read-only browser scans. Explicit apply selects a bounded pending set, including targets from earlier cycles. |
| 0:37.5-0:45 | Decision flow, Page and target verification | For each selected target, I reverify its originating Page and confirm the numeric profile. |
| 0:45-0:52.5 | Sequence diagram, fail-closed block and outcome | I fail closed on uncertainty. Otherwise I submit the Facebook UI block and atomically record submitted, failed, or uncertain. |
| 0:52.5-1:00 | Manual-vs-automated ownership close | This is the complete Monitor, Detect, Deduplicate, Moderate, and Log workflow I designed, built, deployed, and operated. |

## Capture rules

- 1600 x 900, H.264, 30 frames per second, no audio track.
- Embed English captions and keep matching `.srt` and `.vtt` sidecars.
- Use only synthetic art, public diagrams, and the local static showcase.
- Never capture a Facebook session, browser storage state, credentials, identifiers, logs, or local filesystem paths.
- Do not imply that Graph enumerates other users' reactions.

Portfolio visualization based on the implemented workflow.
