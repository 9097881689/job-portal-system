from __future__ import annotations

import html as html_lib
import json
import logging
import re
import signal
from contextlib import contextmanager
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.normalizer import RawJob
from app.core.config import ROOT_DIR, settings
from app.seo.schemas import breadcrumb_schema, faq_schema, job_posting_schema
from app.utils.title_image import title_image_data_uri
from app.utils.job_location import detect_job_location
from app.utils.text import clamp, slugify

logger = logging.getLogger(__name__)


MASTER_CONTENT_PROMPT = """
आप TheDailyJob.in के एक अनुभवी भारतीय सरकारी नौकरी ब्लॉगर और सीनियर एडिटर हैं।
आपका मुख्य काम उम्मीदवारों (job aspirants) के लिए 100% ओरिजिनल, सरल, स्वाभाविक और इंसानी भाषा (Human-Written Style) में जॉब पोस्ट तैयार करना है।

इंसानी स्टाइल के सख्त नियम (Human-Writing Rules):
1. शुरुआत (Opening Hook): आर्टिकल को रोबोटिक या मशीनी न बनाएं। शुरुआत में उम्मीदवार से सीधे बात करते हुए 2-3 लाइन का उत्साहजनक और दोस्ताना ओपनिंग लिखें।
   जैसे: "सरकारी नौकरी की तैयारी कर रहे युवाओं के लिए एक सुनहरा अवसर सामने आया है! [विभाग का नाम] ने [पद का नाम] के पदों पर नई भर्ती का आधिकारिक नोटिफिकेशन जारी किया है..."
2. विश्वसनीयता और असलियत (No Fake Facts): 
   - किसी भी फर्जी या काल्पनिक विभाग का नाम न लिखें।
   - जो जानकारी नोटिफिकेशन में न हो, उसके लिए स्पष्ट रूप से "आधिकारिक नोटिफिकेशन देखें" लिखें।
3. स्वाभाविक भाषा (Natural Hindi + English Job Terms):
   - वाक्य छोटे, सीधे, शुद्ध और स्पष्ट हिंदी (देवनागरी लिपि) में हों।
   - बोलचाल वाले आम सरकारी नौकरी के अंग्रेजी शब्दों को उसी तरह लिखें, जैसे: 'Online Apply', 'Last Date', 'Admit Card', 'Result', 'Syllabus', 'Application Fee', 'Age Limit', 'Eligibility'.
   - कभी भी टूटी-फूटी या गूगल ट्रांसलेट जैसी भद्दी हिंदी न लिखें।
4. उम्मीदवारों के लिए एडिटर की सलाह (Editor Note):
   - उम्मीदवारों को एक सच्चे मार्गदर्शक की तरह सलाह दें कि अंतिम तिथि (Last Date) का इंतजार किए बिना समय रहते फॉर्म सबमिट करें ताकि आखिरी दिनों में सर्वर स्लो होने की समस्या से बचा जा सके।
5. सरल आवेदन प्रक्रिया (How to Apply):
   - 4-5 बहुत ही स्पष्ट और आसान स्टेप्स में बताएं कि फॉर्म कैसे और कहाँ से भरना है।
6. अक्सर पूछे जाने वाले सवाल (FAQs):
   - ऐसे 3-4 प्रश्न और उत्तर तैयार करें जो असल में उम्मीदवार जानना चाहते हैं (जैसे- फॉर्म की लास्ट डेट क्या है? सैलरी कितनी मिलेगी? क्या दूसरे राज्य के कैंडिडेट अप्लाई कर सकते हैं?)।
7. किसी भी प्रतिस्पर्धी वेबसाइट (जैसे SarkariResult, SarkariExam) का नाम या लिंक बिल्कुल न डालें।
""".strip()


@dataclass
class GeneratedArticle:
    title: str
    meta_description: str
    slug: str
    html: str
    faqs: list[dict[str, str]]


class ArticleGenerator:
    """Generate Hindi SEO articles with OpenAI, Gemini, or local template fallback."""

    def __init__(self) -> None:
        self.env = Environment(
            loader=FileSystemLoader(ROOT_DIR / "app" / "templates"),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate(self, job: RawJob, labels: list[str], featured_image: str) -> GeneratedArticle:
        ai_payload = self._clean_ai_payload(self._generate_ai_payload(job, labels))
        title = self._full_title(ai_payload.get("seo_title") or f"{job.title} - आवेदन, योग्यता और पूरी जानकारी")
        meta = clamp(self._strip_source_branding(ai_payload.get("meta_description") or f"{job.title} की पूरी जानकारी, योग्यता, फीस, आयु सीमा और आवेदन लिंक देखें।"), 155)
        slug = slugify(ai_payload.get("seo_slug") or title)
        faqs = self._normalize_faqs(ai_payload.get("faqs"), job)
        important_dates = self._to_mapping(ai_payload.get("important_dates", {}), default_key="date")
        application_fee = ai_payload.get("application_fee", "आधिकारिक नोटिफिकेशन देखें।")
        age_limit = ai_payload.get("age_limit", "आधिकारिक नोटिफिकेशन देखें।")
        qualification = ai_payload.get("educational_qualification", "आधिकारिक नोटिफिकेशन देखें।")
        official_links = self._standard_important_links(ai_payload.get("important_links", []), labels, job)
        job_location = detect_job_location(job)

        draft_post_url = f"{settings.site_base_url}/{slug}.html"
        template = self.env.get_template("article.html")
        html = template.render(
            job=job,
            labels=labels,
            featured_image=featured_image,
            title_image=title_image_data_uri(title, labels),
            image_alt=self._strip_source_branding(ai_payload.get("featured_image_alt", title)),
            image_title=self._strip_source_branding(ai_payload.get("featured_image_title", title)),
            image_caption=self._strip_source_branding(ai_payload.get("featured_image_caption", "")),
            title=title,
            meta_description=meta,
            overview=self._strip_source_branding(ai_payload.get("overview", "")),
            editor_note=self._strip_source_branding(ai_payload.get("editor_note", "")),
            quick_highlights=self._to_list(ai_payload.get("quick_highlights", []), limit=8),
            notification_details=self._strip_source_branding(ai_payload.get("notification_details", "")),
            vacancy_details=self._strip_source_branding(ai_payload.get("vacancy_details", "")),
            important_dates=important_dates,
            job_location=job_location,
            application_fee=application_fee,
            application_fee_items=self._to_bullets(application_fee),
            age_limit=age_limit,
            age_limit_items=self._to_bullets(age_limit),
            qualification=qualification,
            qualification_items=self._to_bullets(qualification),
            selection_process=ai_payload.get("selection_process", "लिखित परीक्षा/मेरिट/इंटरव्यू के आधार पर चयन हो सकता है।"),
            salary=ai_payload.get("salary_details", "नियमों के अनुसार।"),
            required_documents=self._to_list(ai_payload.get("required_documents", []), fallback=self._required_documents(self._article_kind(job)), limit=12),
            how_to_apply=self._to_list(ai_payload.get("how_to_apply", []), fallback=self._default_steps(self._article_kind(job)), limit=10),
            important_links=official_links,
            safe_apply_url=self._safe_official_url(job.apply_url),
            conclusion=self._strip_source_branding(ai_payload.get("conclusion", "")),
            focus_keyword=self._strip_source_branding(ai_payload.get("focus_keyword", job.title)),
            faqs=faqs,
            job_schema=job_posting_schema(job, draft_post_url),
            faq_schema=faq_schema(faqs),
            breadcrumb_schema=breadcrumb_schema(title, labels[0], draft_post_url),
        )
        return GeneratedArticle(title=title, meta_description=meta, slug=slug, html=html, faqs=faqs)

    def _generate_ai_payload(self, job: RawJob, labels: list[str]) -> dict:
        if settings.ai_provider == "openai" and settings.openai_api_key:
            try:
                with _ai_deadline(150):
                    return self._openai_payload(job, labels)
            except Exception as exc:
                logger.warning("OpenAI generation failed; falling back to local template: %s", exc)
        if settings.ai_provider == "gemini" and settings.gemini_api_key:
            for model in self._free_gemini_models():
                try:
                    with _ai_deadline(45):
                        return self._gemini_payload(job, labels, model=model)
                except Exception as exc:
                    logger.warning("Gemini generation failed for %s; trying next free model: %s", model, exc)
            if settings.openrouter_api_key:
                try:
                    with _ai_deadline(35):
                        return self._openrouter_payload(job, labels)
                except Exception as exc:
                    logger.warning("OpenRouter free generation failed; falling back to local template: %s", exc)
        if settings.ai_provider == "deepseek" and settings.deepseek_api_key:
            try:
                with _ai_deadline(45):
                    return self._deepseek_payload(job, labels)
            except Exception as exc:
                logger.warning("DeepSeek generation failed; falling back to local template: %s", exc)
        if settings.ai_provider == "openrouter" and settings.openrouter_api_key:
            try:
                with _ai_deadline(35):
                    return self._openrouter_payload(job, labels)
            except Exception as exc:
                logger.warning("OpenRouter generation failed; falling back to local template: %s", exc)
        return self._template_payload(job)

    @retry(wait=wait_exponential(multiplier=1, min=1, max=2), stop=stop_after_attempt(1))
    def _openai_payload(self, job: RawJob, labels: list[str]) -> dict:
        client = OpenAI(api_key=settings.openai_api_key, max_retries=0)
        payload = {
            "model": settings.openai_model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        MASTER_CONTENT_PROMPT + " "
                        "You write original, human-readable Hindi-English job articles for Blogger. "
                        "Return only valid JSON. Write like a careful human editor, not like an AI summary. "
                        "Use Hindi in Devanagari with natural English terms; do not write Roman Hinglish sentences. "
                        "Sentences must be grammatically natural for Indian readers. Avoid awkward half-English half-Hindi word order. "
                        "Never shorten the title with ellipsis or three dots. "
                        "Do not copy source paragraphs. Do not add SarkariExam/SarkariResult links. "
                        "Use only the provided facts. Never fabricate official facts; use 'Official notification देखें' when unknown."
                    ),
                },
                {"role": "user", "content": self._prompt(job, labels)},
            ],
        }
        if settings.openai_model.startswith("gpt-5"):
            payload["max_completion_tokens"] = 3500
        else:
            payload["temperature"] = 0.7
        response = client.chat.completions.create(**payload)
        return json.loads(response.choices[0].message.content or "{}")

    def _free_gemini_models(self) -> list[str]:
        preferred = [
            settings.gemini_model,
            "gemini-flash-lite-latest",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
        ]
        models: list[str] = []
        for model in preferred:
            model = str(model or "").strip()
            if model and model not in models:
                models.append(model)
        return models

    @retry(wait=wait_exponential(multiplier=1, min=1, max=4), stop=stop_after_attempt(1))
    def _gemini_payload(self, job: RawJob, labels: list[str], model: str | None = None) -> dict:
        selected_model = model or settings.gemini_model
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{selected_model}:generateContent?key={settings.gemini_api_key}"
        )
        response = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": self._prompt(job, labels)}]}],
                "generationConfig": {
                    "temperature": 0.65,
                    "responseMimeType": "application/json",
                },
            },
            timeout=40,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        text = text.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(text)

    @retry(wait=wait_exponential(multiplier=1, min=1, max=6), stop=stop_after_attempt(2))
    def _deepseek_payload(self, job: RawJob, labels: list[str]) -> dict:
        response = requests.post(
            f"{settings.deepseek_base_url.rstrip('/')}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.deepseek_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            MASTER_CONTENT_PROMPT
                            + " Return only valid JSON. Do not wrap JSON in markdown. "
                            + "Use the requested keys exactly and keep every fact grounded in the provided job data."
                        ),
                    },
                    {"role": "user", "content": self._prompt(job, labels)},
                ],
                "temperature": 0.55,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return json.loads(text or "{}")

    @retry(wait=wait_exponential(multiplier=1, min=1, max=2), stop=stop_after_attempt(1))
    def _openrouter_payload(self, job: RawJob, labels: list[str]) -> dict:
        response = requests.post(
            f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": settings.site_base_url,
                "X-Title": settings.site_name or "TheDailyJob",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            MASTER_CONTENT_PROMPT
                            + " Return only valid JSON. Do not wrap JSON in markdown. "
                            + "Write a real, natural article suitable for Indian job readers."
                        ),
                    },
                    {"role": "user", "content": self._prompt(job, labels)},
                ],
                "temperature": 0.55,
                "response_format": {"type": "json_object"},
            },
            timeout=25,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return json.loads(text or "{}")

    def _prompt(self, job: RawJob, labels: list[str]) -> str:
        return json.dumps(
            {
                "instruction": (
                    MASTER_CONTENT_PROMPT + " "
                    "100% unique Hindi-English SEO job article JSON बनाएं. "
                    "भाषा Devanagari Hindi + जरूरी English terms वाली हो, Roman Hinglish नहीं. Example: 'उम्मीदवार Apply Online link से आवेदन कर सकते हैं'. "
                    "वाक्य छोटे, साफ और natural होने चाहिए. टूटी हुई machine translation जैसी language बिल्कुल नहीं. "
                    "Title पूरा लिखें; title में '...' या ellipsis न लगाएं. "
                    "Source content को copy मत करें; facts same रखें but wording पूरी तरह new रखें. Human editor वाली भाषा रखें, AI-style generic lines नहीं. "
                    "SarkariExam/SarkariResult का नाम या link article में मत डालें. "
                    "अगर official/apply link मिले तो only वही important_links में रखें."
                ),
                "style_rules": [
                    "Write like a small Hindi job-news editor: practical, direct, and useful",
                    "Short readable paragraphs in Hindi script with useful English job terms",
                    "Use English terms only for common job words: Apply Online, Official Link, Admit Card, Result, Eligibility, Fee",
                    "Do not mix English grammar into Hindi sentences",
                    "Avoid repeated filler like 'पूरी जानकारी देखें' in every line",
                    "Do not sound promotional or robotic",
                    "Clear table-friendly values",
                    "No fake dates, fee, salary, vacancies, qualification",
                    "No source-site promotion",
                    "FAQ answers concise and useful",
                ],
                "required_keys": [
                    "seo_title",
                    "meta_description",
                    "seo_slug",
                    "overview",
                    "editor_note",
                    "quick_highlights",
                    "featured_image_alt",
                    "featured_image_title",
                    "featured_image_caption",
                    "notification_details",
                    "important_dates",
                    "vacancy_details",
                    "application_fee",
                    "age_limit",
                    "educational_qualification",
                    "selection_process",
                    "salary_details",
                    "required_documents",
                    "how_to_apply",
                    "important_links",
                    "faqs",
                    "conclusion",
                    "focus_keyword",
                ],
                "job": job.__dict__,
                "labels": labels,
            },
            ensure_ascii=False,
            default=str,
        )

    def _clean_ai_payload(self, value: object) -> object:
        if isinstance(value, dict):
            return {str(key): self._clean_ai_payload(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._clean_ai_payload(item) for item in value]
        if isinstance(value, str):
            return self._plain_text(value)
        return value

    def _plain_text(self, value: object) -> str:
        text = str(value or "")
        text = html_lib.unescape(text)
        text = re.sub(r"```(?:html|json|markdown|md)?", "", text, flags=re.IGNORECASE)
        text = text.replace("```", "")
        if re.search(r"</?(div|span|p|h[1-6]|table|tr|td|th|ul|ol|li|script|style|article|section|br)\b", text, flags=re.IGNORECASE):
            text = BeautifulSoup(text, "html.parser").get_text(" ")
        text = re.sub(r"</?[^>]+>", " ", text)
        text = text.replace("{#", " ").replace("#}", " ")
        text = text.replace("{{", " ").replace("}}", " ").replace("{%", " ").replace("%}", " ")
        return " ".join(text.split()).strip(" -|:")

    def _template_payload(self, job: RawJob) -> dict:
        details = job.extra.get("details", {}) if isinstance(job.extra, dict) else {}
        kind = self._article_kind(job)
        important_dates = details.get("important_dates") or {
            "notification": "Official notification के अनुसार update देखें",
            "last_date": "Official notification में दी गई date verify करें",
        }
        application_fee = self._clean_detail(details.get("application_fee")) or "Application Fee category और post के अनुसार अलग हो सकती है. Payment करने से पहले official notification में fee section जरूर देखें."
        age_limit = self._clean_detail(details.get("age_limit")) or "Age Limit recruitment rules के अनुसार तय होगी. Reserved category candidates को official rules के अनुसार relaxation मिल सकता है."
        qualification = self._clean_detail(details.get("educational_qualification")) or "Educational Qualification post के अनुसार अलग हो सकती है. Candidate अपनी education, category और experience detail official notification से जरूर मिलाएं."
        selection_process = self._clean_detail(details.get("selection_process")) or self._selection_text(kind)
        salary = self._clean_detail(details.get("salary_details")) or "Salary/Pay Scale department rules के अनुसार रहेगा. Exact pay level के लिए official notification का salary section देखें."
        how_to_apply = details.get("how_to_apply") or self._default_steps(kind)
        important_links = details.get("important_links") or []
        organization = job.organization or details.get("organization") or "Recruiting Organization"
        post_name = job.post_name or details.get("post_name") or job.title
        vacancies = job.vacancies if job.vacancies != "Not specified" else details.get("vacancies", "Not specified")
        overview, editor_note = self._human_intro(job, organization, post_name, kind)
        focus_keyword = self._focus_keyword(job, kind)

        return {
            "seo_title": self._seo_title(job, kind),
            "meta_description": self._meta_description(job, kind),
            "seo_slug": f"{job.title} online form notification",
            "overview": overview,
            "editor_note": editor_note,
            "quick_highlights": self._quick_highlights(job, labels=[], kind=kind, vacancies=vacancies),
            "featured_image_alt": f"{job.title} TheDailyJob featured image",
            "featured_image_title": f"{job.title} - TheDailyJob",
            "featured_image_caption": f"{job.title} की मुख्य जानकारी TheDailyJob title card में दी गई है.",
            "notification_details": self._notification_details(job, organization, post_name, kind),
            "important_dates": important_dates,
            "vacancy_details": self._vacancy_details(post_name, vacancies),
            "application_fee": application_fee,
            "age_limit": age_limit,
            "educational_qualification": qualification,
            "selection_process": selection_process,
            "salary_details": salary,
            "required_documents": self._required_documents(kind),
            "how_to_apply": how_to_apply,
            "important_links": important_links,
            "faqs": self._default_faqs(job),
            "conclusion": self._conclusion(job, kind),
            "focus_keyword": focus_keyword,
            "organization": organization,
            "post_name": post_name,
            "vacancies": vacancies,
        }

    def _to_list(self, value: object, fallback: list[str] | None = None, limit: int = 10) -> list[str]:
        items: list[str] = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    text = " - ".join(str(part).strip() for part in item.values() if str(part).strip())
                else:
                    text = str(item).strip()
                if text:
                    items.append(self._plain_text(text))
        elif isinstance(value, dict):
            for key, val in value.items():
                if val:
                    items.append(self._plain_text(f"{str(key).replace('_', ' ').title()}: {val}"))
        else:
            text = self._plain_text(value)
            if text:
                parts = self._to_bullets(text)
                if len(parts) <= 1 and "," in text:
                    parts = [piece.strip() for piece in text.split(",") if piece.strip()]
                items.extend(parts if len(parts) > 1 else [text])

        cleaned: list[str] = []
        seen = set()
        for item in items:
            item = " ".join(str(item).split()).strip(" -:;•")
            if not item or len(item) <= 1:
                continue
            # Broken AI output can split Hindi words into single characters; reject those.
            if len(item) < 3 and not any(ch.isdigit() for ch in item):
                continue
            key = item.lower()
            if key not in seen:
                cleaned.append(item)
                seen.add(key)
        if fallback and len(cleaned) < min(3, len(fallback)):
            cleaned = fallback
        return cleaned[:limit]

    def _normalize_faqs(self, value: object, job: RawJob) -> list[dict[str, str]]:
        if isinstance(value, list):
            faqs: list[dict[str, str]] = []
            for item in value:
                if isinstance(item, dict):
                    question = self._plain_text(item.get("question") or item.get("q") or "")
                    answer = self._plain_text(item.get("answer") or item.get("a") or "")
                    if question and answer:
                        faqs.append({"question": question, "answer": answer})
            if faqs:
                return faqs[:7]
        return self._default_faqs(job)

    def _default_faqs(self, job: RawJob) -> list[dict[str, str]]:
        title = job.post_name or job.title
        return [
            {"question": f"{title} का official update कहां मिलेगा?", "answer": "इसका update official website पर notification, Apply Online link, Admit Card या Result section में मिल सकता है."},
            {"question": f"{title} में apply/download से पहले क्या check करें?", "answer": "Date, eligibility, fee, age limit, required documents और official link ध्यान से check करें."},
            {"question": f"{title} की details change हो सकती हैं?", "answer": "हां, department official notice के माध्यम से dates, links या instructions update कर सकता है."},
        ]

    def _article_kind(self, job: RawJob) -> str:
        title = job.title.lower()
        if any(word in title for word in ["admit card", "hall ticket", "call letter", "exam city"]):
            return "admit_card"
        if any(word in title for word in ["result", "score card", "merit list", "cut off"]):
            return "result"
        if any(word in title for word in ["answer key", "response sheet"]):
            return "answer_key"
        if "syllabus" in title:
            return "syllabus"
        return "job"

    def _human_intro(self, job: RawJob, organization: str, post_name: str, kind: str) -> tuple[str, str]:
        title = job.title
        if kind == "result":
            return (
                f"{title} उन candidates के लिए important update है, जिन्होंने इस exam या recruitment process में भाग लिया था. "
                f"Result देखते समय roll number, registration details और official instructions अपने पास रखें.",
                "Result page खोलने से पहले official link और notice date जरूर verify करें. कई बार result PDF, marks और cutoff अलग-अलग समय पर update होते हैं.",
            )
        if kind == "admit_card":
            return (
                f"{title} download करने वाले candidates को exam date, reporting time, exam city और instructions ध्यान से check करनी चाहिए. "
                f"Exam centre पर Admit Card के साथ valid photo ID ले जाना आम तौर पर जरूरी होता है.",
                "Exam centre पर जाने से पहले admit card print, photo ID और notification instructions एक बार जरूर मिला लें.",
            )
        if kind == "answer_key":
            return (
                f"{title} candidates को अपने attempted answers compare करने का मौका देता है. "
                f"अगर objection window खुली हो, तो objection submit करने से पहले question number और proof तैयार रखें.",
                "Answer Key को final result न मानें. Final marks department के final evaluation के बाद ही clear होते हैं.",
            )
        return (
            f"{organization} ने {post_name} से जुड़ा नया recruitment update जारी किया है. "
            f"जो candidates इस post के लिए interested हैं, उन्हें eligibility, age limit, fee, important dates और apply process ध्यान से पढ़ना चाहिए.",
            "Form submit करने से पहले official notification जरूर पढ़ें. Date, category या document से जुड़ी छोटी गलती भी बाद में परेशानी बना सकती है.",
        )

    def _seo_title(self, job: RawJob, kind: str) -> str:
        suffix = {
            "result": "Result, Merit List और Official Link",
            "admit_card": "Admit Card, Exam Date और Download Link",
            "answer_key": "Answer Key, Objection और Download Link",
            "syllabus": "Syllabus, Exam Pattern और PDF Detail",
        }.get(kind, "Apply Online, Eligibility, Dates और Fee")
        return f"{job.title}: {suffix}"

    def _meta_description(self, job: RawJob, kind: str) -> str:
        if kind == "result":
            return f"{job.title} result update, official link, merit list, cutoff और next step की जरूरी details यहां पढ़ें."
        if kind == "admit_card":
            return f"{job.title} Admit Card, exam date, download process और important instructions की details यहां पढ़ें."
        return f"{job.title} की eligibility, important dates, fee, age limit, selection process और official link की साफ जानकारी यहां पढ़ें."

    def _selection_text(self, kind: str) -> str:
        if kind == "result":
            return "Result/Merit List official evaluation के बाद जारी होती है. इसके बाद document verification, medical, interview या final joining notice जारी हो सकता है."
        if kind == "admit_card":
            return "Selection process के next stage के लिए Admit Card जारी किया जाता है. Exam के बाद result या merit list official website पर update होती है."
        return "Selection Process में written exam, skill test, document verification, medical test या merit stage शामिल हो सकते हैं."

    def _default_steps(self, kind: str) -> list[str]:
        if kind == "result":
            return [
                "Official result या download link open करें.",
                "Roll number, registration number या PDF search option से अपना result check करें.",
                "Result PDF save करें और next stage notice carefully पढ़ें.",
                "Document verification या further process के लिए official instructions follow करें.",
            ]
        if kind == "admit_card":
            return [
                "Official Admit Card या download link open करें.",
                "Registration number, date of birth/password से login करें.",
                "Admit Card पर name, exam date, shift, centre और instructions check करें.",
                "Printout निकालें और valid photo ID के साथ exam centre पर जाएं.",
            ]
        return [
            "Official notification को ध्यान से पढ़ें.",
            "Eligibility, fee, age limit और last date confirm करें.",
            "Apply Online link से form fill करें और documents upload करें.",
            "Final submit से पहले preview check करें, फिर receipt/print save कर लें.",
        ]

    def _notification_details(self, job: RawJob, organization: str, post_name: str, kind: str) -> str:
        if kind == "result":
            return (
                f"{post_name} से जुड़ा यह result update official process का हिस्सा है. Candidates को result notice, merit list, "
                f"cutoff और आगे की प्रक्रिया official website से verify करनी चाहिए."
            )
        if kind == "admit_card":
            return (
                f"{post_name} के लिए Admit Card जारी होने पर candidates को exam date, shift, reporting time और centre details "
                f"official admit card से check करनी चाहिए."
            )
        return (
            f"{organization} द्वारा {post_name} के लिए notification जारी किया गया है. इस update में candidates को eligibility, "
            f"application process, important dates और official instructions ध्यान से पढ़ने की जरूरत है."
        )

    def _vacancy_details(self, post_name: str, vacancies: str) -> str:
        if vacancies and vacancies != "Not specified":
            return f"{post_name} के लिए कुल vacancies {vacancies} बताई गई हैं. Category-wise या trade-wise details official notification में verify करें."
        return f"{post_name} की vacancy details official notification में update होती हैं. अगर category-wise details उपलब्ध होंगी तो candidates उसे official notice में देख सकते हैं."

    def _required_documents(self, kind: str) -> list[str]:
        if kind == "result":
            return ["Roll Number / Registration Number", "Admit Card copy", "Valid Photo ID", "Result PDF या marks detail", "Official notice की copy"]
        return [
            "Aadhaar Card या valid Photo ID",
            "Educational certificates",
            "Category certificate, अगर लागू हो",
            "Recent passport size photo",
            "Signature scan copy",
            "Experience/technical certificate, अगर required हो",
            "Application fee payment receipt",
        ]

    def _conclusion(self, job: RawJob, kind: str) -> str:
        if kind == "result":
            return f"{job.title} check करने के बाद candidates को next stage की तैयारी official notice के अनुसार करनी चाहिए. किसी भी final decision से पहले official website जरूर verify करें."
        return f"{job.title} में interested candidates को last date से पहले form submit करना चाहिए. आवेदन करने से पहले eligibility, fee, age limit और official notification जरूर verify करें."

    def _focus_keyword(self, job: RawJob, kind: str) -> str:
        suffix = {
            "result": "Result",
            "admit_card": "Admit Card",
            "answer_key": "Answer Key",
            "syllabus": "Syllabus",
        }.get(kind, "Apply Online")
        return f"{job.title} {suffix}"

    def _quick_highlights(self, job: RawJob, labels: list[str], kind: str, vacancies: str) -> list[str]:
        highlights = [
            f"Update Type: {'Result/Download' if kind == 'result' else 'Online Form/Recruitment' if kind == 'job' else kind.replace('_', ' ').title()}",
            f"Post/Exam: {job.post_name or job.title}",
        ]
        if vacancies and vacancies != "Not specified":
            highlights.append(f"Vacancies: {vacancies}")
        highlights.append("Official details verify करना जरूरी है")
        return highlights

    def _clean_detail(self, value: str | None) -> str:
        if not value:
            return ""
        value = " ".join(str(value).split())
        return self._strip_source_branding(value).strip(" -|")[:1200]

    def _standard_important_links(self, links: object, labels: list[str], job: RawJob | None = None) -> list[dict[str, str]]:
        raw_links = links if isinstance(links, list) else []
        official_notification = self._find_link(raw_links, ["notification", "notice", "pdf"])
        apply_online = self._find_link(raw_links, ["apply", "online"])
        official_website = self._find_link(raw_links, ["official website", "official"])
        admit_card = self._find_link(raw_links, ["admit card", "hall ticket", "call letter"])
        result = self._find_link(raw_links, ["result", "merit", "score", "rank card"])

        fallback_links = self._official_link_fallbacks(job)
        official_notification = official_notification or fallback_links.get("official_notification", "")
        apply_online = apply_online or fallback_links.get("apply_online", "")
        official_website = official_website or fallback_links.get("official_website", "")
        admit_card = admit_card or fallback_links.get("admit_card", "")
        result = result or fallback_links.get("result", "")

        category_label = "Railway Jobs" if "Railway Jobs" in labels else "Government Jobs"
        rows = [
            {"label": "Official Notification", "url": official_notification or "", "text": "Click Here" if official_notification else "Available Soon"},
            {"label": "Apply Online", "url": apply_online or "", "text": "Click Here" if apply_online else "Available Soon"},
            {"label": "Official Website", "url": official_website or "", "text": "Click Here" if official_website else "Available Soon"},
            {"label": "Admit Card", "url": admit_card or "/search/label/Admit%20Card", "text": "Click Here" if admit_card else "Admit Card Updates"},
            {"label": "Result", "url": result or "/search/label/Results", "text": "Click Here" if result else "Result Updates"},
            {"label": f"Latest {category_label}", "url": f"/search/label/{category_label.replace(' ', '%20')}", "text": "View Posts"},
            {"label": "Latest Jobs", "url": "/search/label/Latest%20Jobs", "text": "View Posts"},
        ]
        deduped = []
        seen = set()
        for row in rows:
            key = (row["label"], row["url"])
            if key not in seen:
                deduped.append(row)
                seen.add(key)
        return deduped

    def _official_link_fallbacks(self, job: RawJob | None) -> dict[str, str]:
        if not job:
            return {}
        title = f"{job.title} {job.post_name} {job.source_url}".lower()
        details = job.extra.get("details", {}) if isinstance(job.extra, dict) else {}
        excerpt = str(details.get("source_excerpt", "")).lower() if isinstance(details, dict) else ""
        combined = f"{title} {excerpt}"

        if "dece" in combined and "le" in combined and "bcece" in combined:
            return {
                "official_notification": "https://bceceboard.bihar.gov.in/pdf_Adv/ADV_DLE26_04.pdf",
                "official_website": "https://bceceboard.bihar.gov.in/",
                "result": "https://bceceboard.bihar.gov.in/web_RankCard/DLE2026_RANK/DLE_Merit.php",
            }
        return {}

    def _safe_official_url(self, url: object) -> str:
        url_text = str(url or "").strip()
        if not url_text:
            return ""
        blocked = ["sarkariresult.com.cm", "sarkariexam.com", "play.google.com", "x.com", "twitter.com", "facebook.com", "instagram.com", "youtube.com", "telegram", "whatsapp"]
        if any(domain in url_text.lower() for domain in blocked):
            return ""
        return url_text

    def _find_link(self, links: list, keywords: list[str]) -> str:
        blocked = ["sarkariresult.com.cm", "sarkariexam.com", "play.google.com", "x.com", "twitter.com", "facebook.com", "instagram.com", "youtube.com", "telegram", "whatsapp"]
        for item in links:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            label = str(item.get("label", "")).lower()
            haystack = f"{label} {url.lower()}"
            if not url or any(word in haystack for word in blocked):
                continue
            if any(keyword in haystack for keyword in keywords):
                return url
        return ""

    def _strip_source_branding(self, value: object) -> str:
        text = str(value or "")
        noisy = [
            "Sarkari Result™",
            "Sarkari Result",
            "SarkariExam",
            "Sarkari Exam",
            "sarkariresult.com.cm",
            "sarkariexam.com",
            "WhatsApp",
            "Telegram",
            "Follow Now",
            "Join Now",
        ]
        for word in noisy:
            text = text.replace(word, "")
        return " ".join(text.split()).strip(" -|:")

    def _to_bullets(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip(" -:") for item in value if str(item).strip()]
        if isinstance(value, dict):
            return [f"{str(key).replace('_', ' ').title()}: {val}" for key, val in value.items() if val]
        text = str(value or "").strip()
        if not text:
            return []

        text = text.replace("।", ".")
        chunks = []
        for part in text.splitlines():
            chunks.extend(part.split("."))

        items: list[str] = []
        for chunk in chunks:
            chunk = chunk.strip(" -:;")
            if not chunk:
                continue
            if len(chunk) > 180 and "," in chunk:
                items.extend(piece.strip(" -:;") for piece in chunk.split(",") if piece.strip())
            else:
                items.append(chunk)

        if len(items) <= 1:
            for sep in ["; ", " | ", " / "]:
                if sep in text:
                    items = [piece.strip(" -:;") for piece in text.split(sep) if piece.strip()]
                    break

        return items[:10]

    def _to_mapping(self, value: object, default_key: str = "detail") -> dict[str, str]:
        if isinstance(value, dict):
            return {str(key): str(val) for key, val in value.items() if val}
        if isinstance(value, list):
            result: dict[str, str] = {}
            for index, item in enumerate(value, 1):
                if isinstance(item, dict):
                    for key, val in item.items():
                        if val:
                            result[str(key)] = str(val)
                elif str(item).strip():
                    result[f"{default_key}_{index}"] = str(item).strip()
            return result
        text = str(value or "").strip()
        return {default_key: text} if text else {"details": "Official notification देखें"}

    def _full_title(self, value: object) -> str:
        title = self._strip_source_branding(value)
        title = title.replace("...", "").replace("…", "").strip(" -|:")
        return title or "Job Update - पूरी जानकारी"

@contextmanager
def _ai_deadline(seconds: int):
    """Stop slow AI providers so cron can fall back instead of blocking."""

    if not hasattr(signal, "SIGALRM"):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)

    def _raise_timeout(signum, frame):
        raise TimeoutError(f"AI generation exceeded {seconds} seconds")

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)
