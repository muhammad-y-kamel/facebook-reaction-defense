# Optional English narration

I built this automation to defend Facebook Pages against coordinated Angry and Haha reaction abuse.

My process loop checks optional Page ratings first through Graph; a new Arabic keyword match may alert but never enters blocking. I use Graph only to discover post and comment identifiers. Authenticated Playwright then scans reaction-browser pages within configured page and actor caps. It requires an Angry or Haha label and its configured icon-source marker before accepting a numeric profile link. Atomic JSON state keeps one target per Page account under an exclusive flock and uses atomic replacement when it saves.

Detection-only is the default. It makes authenticated browser reads and records signals, but it makes no moderation mutation. Repeated observations do not remove a pending target's eligibility. When I explicitly enable apply mode, the workflow selects a bounded set of pending targets, including targets created in earlier cycles. For each selected target, Playwright reverifies its originating Page and confirms the numeric profile. If identity is uncertain, the system fails closed and submits nothing.

After verification, the automation submits the block through the Facebook UI, records the result, and can send a concise Telegram notification.

I designed, built, deployed, and operated this complete workflow.
