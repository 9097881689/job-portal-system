# Deployment Guide

## VPS Deployment

```bash
sudo apt update
sudo apt install -y python3 python3-venv
cd /var/www/job-portal-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/setup_db.py
python -m app.main --dry-run --limit 2
```

Add cron:

```bash
crontab -e
*/30 * * * * cd /var/www/job-portal-system && /bin/bash scripts/cron.sh >> logs/cron.log 2>&1
```

## MySQL

Create a database and update `.env`:

```env
DATABASE_URL=mysql+pymysql://job_user:strong_password@localhost:3306/job_portal
```

Then run:

```bash
python scripts/setup_db.py
```

## Security Notes

- Keep `.env`, OAuth credentials, and tokens private.
- Use draft mode until the generated article quality has been reviewed.
- Prefer official recruitment sources to avoid misinformation.
- Replace demo sources with your verified RSS/API URLs.
