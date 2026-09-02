# GitHub Actions Auto Posting Setup

Ye setup karne ke baad TheDailyJob ka auto post GitHub server se chalega. Laptop band rahe tab bhi GitHub Actions schedule ke hisab se source check karega.

## 1. Sabse pehle private GitHub repo banaye

Repo **private** rakhiye, kyunki Blogger token aur current duplicate database project ke andar use hota hai.

## 2. Project GitHub me upload kare

Is folder ko GitHub repo me upload/push kare:

```text
/Users/aksingh/CodexJobPortal/job-portal-system
```

Important: Agar current `data/job_portal.db` repo me upload nahi hoga to GitHub ka first run purane posts ko dobara detect kar sakta hai. Duplicate se bachne ke liye private repo me current `data/job_portal.db` bhi upload karna best hai.

## 3. GitHub Secrets add kare

GitHub repo open kare:

```text
Settings > Secrets and variables > Actions > New repository secret
```

Ye secrets add kare:

| Secret name | Kya paste karna hai |
| --- | --- |
| `BLOGGER_CLIENT_SECRET_JSON` | `config/google_client_secret.json` file ka pura content |
| `BLOGGER_TOKEN_JSON` | `config/blogger_token.json` file ka pura content |
| `GEMINI_API_KEY` | Gemini API key, agar available ho |
| `OPENAI_API_KEY` | Optional |
| `DEEPSEEK_API_KEY` | Optional |
| `OPENROUTER_API_KEY` | Optional |

Sirf Blogger ke 2 secrets compulsory hain. AI key nahi rahegi to system local template se article banayega.

## 4. Manual test run kare

GitHub repo me:

```text
Actions > TheDailyJob Blogger Auto Post > Run workflow
```

Limit `10` rakhe. Run complete hone ke baad logs check kare.

## 5. Auto schedule

Workflow abhi har 15 minute par set hai:

```text
*/15 * * * *
```

GitHub free account me schedule exact 15 minute par kabhi-kabhi delay ho sakta hai. Lekin laptop on rakhne ki zarurat nahi hogi.

## 6. Local laptop cron ka dhyan rakhe

Jab GitHub Actions sahi chalne lage, laptop wala cron band karna better hai. Dono saath chale to ek hi time me duplicate/update conflict ka chance badhta hai.

Local cron dekhne ke liye:

```bash
crontab -l
```

Local cron band karne ke liye mujhe bol sakte hain: `local autopost band karo`.

## 7. Log kaise dekhe

GitHub me:

```text
Actions > Latest run > Run Blogger autopost
```

Aur run ke bottom me artifact milega:

```text
autopost-logs-...
```

Usme `autopost.log` aur app logs mil jayenge.
