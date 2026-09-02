from app.utils.text import slugify


def test_slugify_keeps_readable_words():
    assert slugify("Railway Recruitment 2026 Notification!") == "railway-recruitment-2026-notification"
