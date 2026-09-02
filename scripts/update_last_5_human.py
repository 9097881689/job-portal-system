import os
import re
import json
import urllib.request
from app.collectors.normalizer import RawJob
from app.ai.generator import ArticleGenerator

# Read token
with open("/Users/aksingh/Library/Preferences/.wrangler/config/default.toml", "r") as f:
    text = f.read()

m = re.search(r'oauth_token\s*=\s*"([^"]+)"', text)
token = m.group(1)
account_id = "07003637b69052c6ffb6626d5df17aa2"
db_id = "9646d6f8-28ed-4444-86e9-18428cbbfe72"
d1_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{db_id}/query"

posts_data = [
    {
        "id": 1,
        "title": "NVS Class 9th Admission Form 2027-28",
        "org": "Navodaya Vidyalaya Samiti (NVS)",
        "post_name": "Class 9th Lateral Entry Selection Test",
        "vacancies": "Seats as per NVS JNV Rules",
        "apply_url": "https://cbseitms.nic.in/2026/nvsix_9",
        "labels": ["Latest Jobs", "Admission"],
        "extra_summary": "Navodaya Vidyalaya Samiti (NVS) ne Class 9th Lateral Entry Admission 2027-28 ke liye official notification aur online application form release kar diya hai. Eligible students 30 September 2026 tak official website par apply kar sakte hain."
    },
    {
        "id": 2,
        "title": "MP Police SI & Subedar Recruitment 2026 Apply Online for 507 Posts",
        "org": "Madhya Pradesh Employees Selection Board (MPESB)",
        "post_name": "Sub Inspector (SI) & Subedar",
        "vacancies": "507 Posts",
        "apply_url": "https://esb.mp.gov.in",
        "labels": ["Government Jobs", "Latest Jobs"],
        "extra_summary": "Madhya Pradesh Police me Sub Inspector aur Subedar ke kul 507 pado par barti ka notification MPESB ne jari kiya hai. Graduate pass candidates 23 September 2026 tak online aavedan kar sakte hain."
    },
    {
        "id": 3,
        "title": "NIC Scientific / Technical Assistant Recruitment 2026: Apply Online, Eligibility, Dates और Fee",
        "org": "National Informatics Centre (NIC)",
        "post_name": "Scientific / Technical Assistant",
        "vacancies": "Various Posts",
        "apply_url": "https://www.nic.in",
        "labels": ["Government Jobs", "Latest Jobs"],
        "extra_summary": "National Informatics Centre (NIC) ne Scientific Assistant aur Technical Assistant pado ke liye online aavedan shuru kar diye hain. BE/B.Tech/MCA/M.Sc degree holders 30 September 2026 tak aavedan kar sakte hain."
    },
    {
        "id": 4,
        "title": "CONCOR MT, Assistant Officer Recruitment 2026: 77 Posts Apply Online",
        "org": "Container Corporation of India (CONCOR)",
        "post_name": "Management Trainee (MT) & Assistant Officer",
        "vacancies": "77 Posts",
        "apply_url": "https://concorindia.co.in",
        "labels": ["Government Jobs", "Latest Jobs"],
        "extra_summary": "Container Corporation of India Ltd (CONCOR) ne Management Trainee aur Assistant Officer ke 77 pado ke liye vacancy nikali hai. Sambandhit vishay me Graduate/CA/MBA pass candidates online apply kar sakte hain."
    },
    {
        "id": 5,
        "title": "NVS Class 11th Admission Form 2027-28",
        "org": "Navodaya Vidyalaya Samiti (NVS)",
        "post_name": "Class 11th Lateral Entry Admission",
        "vacancies": "Seats as per JNV Vacancy",
        "apply_url": "https://cbseitms.nic.in/2026/nvsxi_11",
        "labels": ["Latest Jobs", "Admission"],
        "extra_summary": "Jawahar Navodaya Vidyalaya Samiti (NVS) ne Class 11th Lateral Entry Admission Test 2027-28 ka notification aur online form jari kiya hai. Class 10th pass vidyarthi 30 September 2026 tak registration kar sakte hain."
    }
]

generator = ArticleGenerator()

for p in posts_data:
    post_id = p["id"]
    print(f"\n==========================================")
    print(f"Generating Human-Style Article for ID {post_id}: {p['title']}...")
    
    raw_job = RawJob(
        source_name="TheDailyJob",
        source_job_id=str(post_id),
        title=p["title"],
        source_url=p["apply_url"],
        organization=p["org"],
        post_name=p["post_name"],
        vacancies=p["vacancies"],
        apply_url=p["apply_url"],
        summary=p["extra_summary"]
    )
    
    article = generator.generate(raw_job, p["labels"], "")
    html_content = article.html
    title = article.title
    
    payload = json.dumps({
        "sql": "UPDATE posts SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        "params": [title, html_content, post_id]
    }).encode("utf-8")
    
    req = urllib.request.Request(d1_url, data=payload, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("success"):
                print(f"✅ Successfully updated ID {post_id} in D1 database!")
            else:
                print(f"❌ Error updating ID {post_id}:", res.get("errors"))
    except Exception as e:
        print(f"❌ Exception for ID {post_id}:", e)

print("\n🎉 All 5 posts have been successfully regenerated and updated in Human Style!")
