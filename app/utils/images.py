from __future__ import annotations

from app.core.config import settings


def featured_image_for_labels(labels: list[str]) -> str:
    """Return a fast external featured image URL.

    Replace this mapping with your own Blogger-hosted image URLs for best performance.
    """

    mapping = {
        "Railway Jobs": settings.default_featured_image,
        "Bank Jobs": settings.default_featured_image,
        "Defence Jobs": settings.default_featured_image,
        "Admit Card": settings.default_featured_image,
        "Results": settings.default_featured_image,
    }
    for label in labels:
        if label in mapping:
            return mapping[label]
    return settings.default_featured_image
