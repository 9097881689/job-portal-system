# Automated Job Portal System for Blogger

Production-ready Python starter for a Blogger-based automated job portal. It collects jobs from RSS feeds, JSON APIs, or configured official sources, prevents duplicate posts, generates unique Hindi SEO articles, adds schema markup, and publishes to Blogger through Blogger API v3.

## Features

- Blogger/Blogspot publishing with custom-domain compatibility.
- Mobile-friendly Blogger article HTML.
- RSS, API, and predefined source collection.
- Duplicate prevention with stored SHA-256 job fingerprints.
- SQLite by default, MySQL supported through SQLAlchemy.
- AI article generation through OpenAI, Gemini, or local template fallback.
- Hindi article sections: overview, organization, post, vacancies, dates, fee, age, qualification, selection, salary, how to apply, links, FAQ.
- SEO title, meta description, slug, FAQ schema, JobPosting schema, breadcrumb schema, labels, internal links, related category links.
- Automatic labels for Latest Jobs, Government Jobs, Railway Jobs, Bank Jobs, Defence Jobs, State Government Jobs, Private Jobs, Admit Card, Results, Answer Key, and Syllabus.
- Draft, instant publish, or scheduled publish mode.
- Existing Blogger posts are updated when the same job receives changed source details.
- Rotating logs, retry handling, dry-run mode, and cron automation.
- Optional Telegram and Facebook auto sharing.

## Project Structure

```text
job-portal-system/
  app/
    ai/                 # OpenAI/Gemini/template article generation
    blogger/            # Blogger API integration
    collectors/         # RSS, API, predefined job collectors
    core/               # Settings and logging
    db/                 # SQLAlchemy session and raw schema
    models/             # Database models
    seo/                # Schema.org JSON-LD helpers
    services/           # Pipeline, duplicate checks, labels, social sharing
    templates/          # Blogger article HTML template
    utils/              # Slug and image helpers
  config/
    sources.yaml        # Job source configuration
    categories.yaml     # Label keyword rules
    blogger-homepage-snippet.html
  data/                 # SQLite database location
  docs/                 # Setup, deployment, cron, SEO docs
  logs/                 # Runtime logs
  scripts/              # Setup and cron scripts
  tests/
```

## Quick Start

```bash
cd /path/to/job-portal-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/setup_db.py
python -m app.main --dry-run --limit 2
```

Edit `.env` and set Blogger credentials before live publishing:

```env
BLOGGER_BLOG_ID=your_blog_id
BLOGGER_CLIENT_SECRETS_FILE=config/google_client_secret.json
PUBLISH_MODE=draft
AI_PROVIDER=template
SITE_BASE_URL=https://www.yourdomain.com
```

Run live:

```bash
python -m app.main --limit 5
```

## Configure Job Sources

Edit `config/sources.yaml`.

Website scraper source:

```yaml
website_sources:
  - name: SarkariExam
    base_url: https://www.sarkariexam.com/
    listing_urls:
      - https://www.sarkariexam.com/
      - https://www.sarkariexam.com/category/top-online-form/
      - https://www.sarkariexam.com/category/admit-card/
      - https://www.sarkariexam.com/category/exam-result/
    enabled: true
    priority: 1
    max_items: 25
    category_hint: Latest Jobs
```

Lower `priority` runs first. The app stores a canonical job key, so the same job is not posted again. If a known job changes later, the old Blogger post is patched instead of creating a repeated post.

RSS source:

```yaml
rss_sources:
  - name: Example Jobs
    url: https://example.com/feed/
    enabled: true
    category_hint: Latest Jobs
```

JSON API source:

```yaml
api_sources:
  - name: Example API
    url: https://example.com/jobs.json
    enabled: true
    id_field: id
    title_field: title
    url_field: apply_url
    date_field: published_at
    category_hint: Private Jobs
```

Manual official source:

```yaml
predefined_sources:
  - id: up-police-constable-2026
    title: UP Police Constable Recruitment 2026
    organization: UP Police
    post_name: Constable
    vacancies: "To be announced"
    apply_url: https://uppbpb.gov.in/
    source_url: https://uppbpb.gov.in/
    category_hint: State Government Jobs
    enabled: true
```

## AI Mode

Template mode is safest for first setup:

```env
AI_PROVIDER=template
```

OpenAI:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
```

Gemini:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-1.5-flash
```

The generator is instructed not to invent official facts. Unknown details are rendered as `आधिकारिक नोटिफिकेशन देखें`.

## Database Schema

Raw SQL is in `app/db/schema.sql`. SQLAlchemy creates the same tables automatically:

- `processed_jobs`: stores source IDs, fingerprints, status, Blogger post IDs, and errors.
- `published_posts`: stores generated SEO title, slug, labels, canonical URL, and Blogger post ID.

## Blogger Homepage

Use `config/blogger-homepage-snippet.html` for search and category navigation. Blogger already provides pagination on index and label pages. Add label widgets for:

- Latest Jobs
- Trending Jobs
- Admit Card
- Results
- Government Jobs
- Railway Jobs
- Bank Jobs
- Defence Jobs

## Deployment and Cron

See:

- `docs/BLOGGER_SETUP.md`
- `docs/DEPLOYMENT.md`
- `docs/CRON.md`
- `docs/SEO_AND_BLOGGER_THEME.md`

## Production Checklist

- Replace demo sources with verified official sources.
- Keep `.env`, `config/google_client_secret.json`, and `config/blogger_token.json` private.
- Start in `PUBLISH_MODE=draft`.
- Review generated content quality before instant publishing.
- Add custom images hosted on Blogger/CDN.
- Submit sitemap in Google Search Console.
- Monitor `logs/job_portal.log` and `logs/cron.log`.
