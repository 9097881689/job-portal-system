# Blogger API Setup

1. Open Google Cloud Console and create a project.
2. Enable **Blogger API v3**.
3. Configure OAuth consent screen.
4. Create OAuth Client ID with type **Desktop app**.
5. Download the JSON file as `config/google_client_secret.json`.
6. Copy `.env.example` to `.env` and set `BLOGGER_BLOG_ID`.
7. Run:

```bash
python -m app.main --dry-run --limit 1
python -m app.main --limit 1
```

On first live run, Google opens an OAuth login flow and saves `config/blogger_token.json`.

Publishing modes:

- `PUBLISH_MODE=draft`: sends posts as Blogger drafts.
- `PUBLISH_MODE=publish`: publishes instantly.
- `PUBLISH_MODE=schedule`: sends scheduled posts when Blogger accepts the scheduled timestamp.
