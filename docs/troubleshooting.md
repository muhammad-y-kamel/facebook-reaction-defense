# Troubleshooting

Start with:

```bash
python reaction_defense.py check-config
```

## `META_PAGES_JSON` is invalid

Use a JSON array of objects with exactly `id`, `name`, `url`, and `access_token`. Quote the whole value. Keep real values private.

## Graph discovery fails

Check `META_GRAPH_VERSION`, token expiry, Page permissions, Page ID, network access, and timeout. Credentials use bearer headers. Graph discovers posts, optional comments, and optional ratings; do not expect it to enumerate other users' reactions.

## Monitoring says browser storage is required

That is expected for every `run`, even without `--apply`. Detection reads the authenticated Facebook reaction browser. Create storage state from an authorized session, store it outside the repository, and set `BROWSER_STORAGE_STATE`. It must be a regular mode-`0600` Playwright JSON file no larger than 5,000,000 bytes inside a mode-`0700` directory. `check-config` and state-only commands do not require it.

## No Angry/Haha targets appear

Verify all of these in an authorized current session:

- `REACTION_TYPES` contains the intended keys.
- `FACEBOOK_REACTION_LABELS_JSON` has exactly those keys and the current visible DOM labels.
- `FACEBOOK_REACTION_ICON_SRC_MARKERS_JSON` has exactly those keys and verified icon-source substrings.
- `FACEBOOK_REACTION_MORE_TEXT` matches the current pagination control.
- The mbasic reaction-browser route accepts the discovered post or comment object.
- Reaction links resolve to numeric `profile.php?id=` targets.
- `MAX_REACTION_BROWSER_PAGES_PER_CYCLE`, `MAX_REACTION_ACTORS_PER_OBJECT`, `MAX_EDGE_PAGES`, and the Graph request share are not excluding the activity.

The UI path is fixed-order and bounded, so sustained early content can defer later objects. Current Meta documentation does not supply this workflow with Graph enumeration of other users' reactions.

## Ratings alert but do not create moderation targets

That is expected. Ratings keywords are alert-only.

## Browser collection or a selector fails

Run visibly with `BROWSER_HEADLESS=false` on an authorized non-production Page. Compare the configured reaction labels, icon-source markers, more-results text, Page-switch text, moderation text, routes, and selectors with the current DOM. Do not weaken identity or numeric-profile validation to force continuation.

## Detection changed Facebook unexpectedly

Detection-only must make authenticated reads and local state updates but no moderation mutation. Stop the process and inspect the invocation: only explicit `--apply` enables the block path.

## A state or lock permission error appears

Use absolute writable paths owned by the service account. The runtime directory should be mode `0700`; state, lock, browser storage, log, environment file, and backups should be mode `0600`. Do not use world-writable permissions.

## State JSON is rejected

Do not hand-edit operational state while the process is running. Restore a known-good private backup or reconcile the strict versioned structure offline. Invalid, duplicate, oversized, or unexpected fields are rejected rather than silently accepted.

## Failed or uncertain actions remain

Inspect the originating Page and private log first. Then use the exact state path and explicit commands:

```bash
python reaction_defense.py retry-failed --state /absolute/private/path/reaction-defense-state.json --confirm RETRY_FAILED_ACTIONS
python reaction_defense.py incomplete --state /absolute/private/path/reaction-defense-state.json
python reaction_defense.py incomplete --state /absolute/private/path/reaction-defense-state.json --show-identifiers --confirm SHOW_PRIVATE_IDENTIFIERS
python reaction_defense.py resolve-incomplete TARGET_REF requeue --state /absolute/private/path/reaction-defense-state.json --confirm RESOLVE_INCOMPLETE_ACTION
```

Use `requeue` only after confirming no Page action occurred; use `submitted` after confirming it did.

## Telegram summaries are missing

Verify both Telegram values and network access. Notification failure does not erase local state, authorize moderation, or change detection behavior.
