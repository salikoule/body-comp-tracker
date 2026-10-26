from routing import router
"""Exact Lucide 1.60.0 paths from body-comp (Beef, Droplets, Wheat, Flame, …)."""

_ATTRS = (
    'class="bc-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"'
)


def _svg(inner):
    return "<svg %s>%s</svg>" % (_ATTRS, inner)


def _path(d):
    return '<path d="%s"/>' % d


def _circle(cx, cy, r):
    return '<circle cx="%s" cy="%s" r="%s"/>' % (cx, cy, r)


ICON = {
    "down": _svg(_path("M16 17h6v-6") + _path("m22 17-8.5-8.5-5 5L2 7")),
    "up": _svg(_path("M16 7h6v6") + _path("m22 7-8.5 8.5-5-5L2 17")),
    "reverse": _svg(
        _path("M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8") + _path("M3 3v5h5")
    ),
    "scale": _svg(
        _path("M12 3v18")
        + _path("m19 8 3 8a5 5 0 0 1-6 0zV7")
        + _path("M3 7h1a17 17 0 0 0 8-2 17 17 0 0 0 8 2h1")
        + _path("m5 8 3 8a5 5 0 0 1-6 0zV7")
        + _path("M7 21h10")
    ),
    "flame": _svg(
        _path("M12 3q1 4 4 6.5t3 5.5a1 1 0 0 1-14 0 5 5 0 0 1 1-3 1 1 0 0 0 5 0c0-2-1.5-3-1.5-5q0-2 2.5-4")
    ),
    "protein": _svg(
        _path("M16.4 13.7A6.5 6.5 0 1 0 6.28 6.6c-1.1 3.13-.78 3.9-3.18 6.08A3 3 0 0 0 5 18c4 0 8.4-1.8 11.4-4.3")
        + _path("m18.5 6 1.754 3.5a6.48 6.48 0 0 1-1.854 8.2C15.4 20.2 11 22 7 22a3 3 0 0 1-2.68-1.66L2.4 16.5")
        + _circle("12.5", "8.5", "2.5")
    ),
    "fat": _svg(
        _path("M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05z")
        + _path("M12.56 6.6A10.97 10.97 0 0 0 14 3.02c.5 2.5 2 4.9 4 6.5s3 3.5 3 5.5a6.98 6.98 0 0 1-11.91 4.97")
    ),
    "carbs": _svg(
        _path("M2 22 16 8")
        + _path("M3.47 12.53 5 11l1.53 1.53a3.5 3.5 0 0 1 0 4.94L5 19l-1.53-1.53a3.5 3.5 0 0 1 0-4.94Z")
        + _path("M7.47 8.53 9 7l1.53 1.53a3.5 3.5 0 0 1 0 4.94L9 15l-1.53-1.53a3.5 3.5 0 0 1 0-4.94Z")
        + _path("M11.47 4.53 13 3l1.53 1.53a3.5 3.5 0 0 1 0 4.94L13 11l-1.53-1.53a3.5 3.5 0 0 1 0-4.94Z")
        + _path("M20 2h2v2a4 4 0 0 1-4 4h-2V6a4 4 0 0 1 4-4Z")
        + _path("M11.47 17.47 13 19l-1.53 1.53a3.5 3.5 0 0 1-4.94 0L5 19l1.53-1.53a3.5 3.5 0 0 1 4.94 0Z")
        + _path("M15.47 13.47 17 15l-1.53 1.53a3.5 3.5 0 0 1-4.94 0L9 15l1.53-1.53a3.5 3.5 0 0 1 4.94 0Z")
        + _path("M19.47 9.47 21 11l-1.53 1.53a3.5 3.5 0 0 1-4.94 0L13 11l1.53-1.53a3.5 3.5 0 0 1 4.94 0Z")
    ),
}

PHASE_ICON = {"cut": "down", "reverse": "reverse", "bulk": "up", "recomp": "scale"}
PHASE_TONE = {"cut": "accent", "reverse": "warn", "bulk": "ok", "recomp": "muted"}
