# Facebook Reaction Abuse Defense showcase

This static portfolio presents the monitoring and moderation workflow I designed, built, deployed, and operated. It uses no analytics, forms, credentials, cookies, or external requests.

The workflow shown uses Graph for Page-object discovery and authenticated Playwright for bounded reaction-browser reads. A numeric profile is accepted only when its Angry/Haha label and configured icon-source marker both match. Detection makes no moderation mutation; explicit apply enables the Page-scoped action.

Preview it locally from the repository root:

```bash
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000/showcase/`. The page follows the browser's light or dark color preference.
