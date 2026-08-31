# Visual plan: Facebook Page Reaction Abuse Defense

## Purpose

I use this visual system to present the automation I designed, built, deployed, and operated. The page explains the operational problem, the implemented workflow, the safety boundary around moderation, and my ownership of the system.

Required public title:

**Facebook Page Reaction Abuse Monitoring and Moderation Automation**

Short title:

**Angry/Haha Reaction Abuse Defense for Facebook Pages**

Role:

**Original Creator and Automation Developer**

Workflow line:

**Monitor → Detect → Deduplicate → Moderate → Log**

## Design direction

- Page type: developer portfolio for technical buyers, collaborators, and hiring teams.
- Tone: operational, credible, direct, and calm.
- Layout: asymmetric split hero, compact problem framing, full-width architecture, horizontal operating loop, decision diagram, and an ownership close.
- Signature: Graph object discovery feeding an authenticated reaction-browser scan with label-and-icon validation, then deduplication and a deliberate moderation gate.
- Motion: static by default, with native hover and focus feedback only.
- Radius: one 14 px radius across images, controls, and containers.

### Color tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| Background | `#EEF2F5` | `#0B1320` | Page canvas |
| Surface | `#F8FAFB` | `#111D2C` | Grouped content |
| Ink | `#0B1320` | `#EEF2F5` | Primary text |
| Muted | `#4C5B6B` | `#AEBDCA` | Supporting text |
| Cobalt | `#315CE7` | `#7796FF` | Primary accent and action path |
| Coral | `#B94238` | `#F07B6F` | Abuse signals and fail-closed states only |

Typography uses the local Aptos or Segoe UI Variable families, with native sans-serif fallbacks and Cascadia Mono for operational labels. No remote font request is required.

## Visual truth boundaries

- Every Page, post, comment, profile, reaction, rating, and account reference is synthetic or generic.
- No access token, browser cookie, storage-state value, private identifier, URL, log entry, or production screenshot appears.
- I do not show a Graph API block endpoint. Blocking is correctly shown as a Facebook UI action submitted through Playwright.
- I do not show Graph enumerating other users' reactions. Graph discovers Page objects; authenticated Playwright reads the reaction browser and requires a configured label plus icon-source marker before accepting a numeric profile.
- Page ratings remain a separate Arabic-keyword alert-only path.
- The optional ratings check appears first in the runtime sequence, before posts and comments.
- Detection-only is the default branch. It still performs read-only browser collection; moderation mutation requires explicit `--apply` mode.
- Observation deduplication never removes a target's stored status. Explicit apply selects bounded targets whose status is `pending`, including targets created in earlier detection-only cycles.
- Every selected target is scoped to its originating Page, and Page identity is reverified before the UI block. Uncertain identity fails closed.
- No production volume, success rate, uptime, or business impact number is invented.
- Every major visual carries the statement: `Portfolio visualization based on the implemented workflow.`

## Asset set

1. Abstract hero image with no baked text or platform branding.
2. Responsive static showcase in light and dark system themes.
3. Architecture, operational sequence, moderation decision, and manual-vs-automated workflow diagrams.
4. Exact-size marketplace covers and responsive showcase captures.
5. A 60-second silent walkthrough with embedded English captions and matching SRT and VTT sidecar files.

## Portfolio visualization based on the implemented workflow.
