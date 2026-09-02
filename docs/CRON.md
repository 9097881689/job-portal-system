# Cron Automation

Run the portal every 30 minutes:

```cron
*/30 * * * * cd /absolute/path/job-portal-system && /bin/bash scripts/cron.sh >> logs/cron.log 2>&1
```

Run once per day at 7 AM:

```cron
0 7 * * * cd /absolute/path/job-portal-system && /bin/bash scripts/cron.sh >> logs/cron.log 2>&1
```

Useful commands:

```bash
crontab -e
crontab -l
python -m app.main --dry-run --limit 3
```
