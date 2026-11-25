#!/usr/bin/env python3
"""Generate GitHub stats and top-languages SVG cards using only the stdlib.

Runs inside GitHub Actions with the built-in GITHUB_TOKEN, so no third-party
service is involved. Usage:
    GH_USER=name GITHUB_TOKEN=... python stats.py [outdir]
    python stats.py --demo [outdir]      # offline render with sample data
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

API = "https://api.github.com"

BG, BORDER = "#141321", "#2d2a4a"
TITLE, TEXT, MUTED, ACCENT = "#a78bfa", "#e5e7eb", "#9ca3af", "#8b5cf6"

LANG_COLORS = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "HTML": "#e34c26",
    "CSS": "#663399", "Python": "#3572a5", "GLSL": "#5686a5", "Shell": "#89e051",
    "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "Go": "#00add8",
    "Rust": "#dea584", "Vue": "#41b883", "SCSS": "#c6538c", "Jupyter Notebook": "#da5b0b",
}
FALLBACK_COLORS = ["#8b5cf6", "#a78bfa", "#6d28d9", "#c4b5fd", "#7c3aed", "#ddd6fe"]


def get(path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


def safe(fn, default="n/a"):
    try:
        return fn()
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        print(f"warning: {exc}", file=sys.stderr)
        return default


def collect(user):
    profile = get(f"/users/{user}")
    repos = []
    page = 1
    while True:
        batch = get(f"/users/{user}/repos", {"per_page": 100, "page": page, "type": "owner"})
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]

    langs = {}
    for r in own[:60]:
        data = safe(lambda r=r: get(f"/repos/{user}/{r['name']}/languages"), {})
        for name, size in data.items():
            langs[name] = langs.get(name, 0) + size

    def count(path, q):
        return get(path, {"q": q, "per_page": 1})["total_count"]

    return {
        "stars": sum(r["stargazers_count"] for r in own),
        "repos": profile["public_repos"],
        "followers": profile["followers"],
        "commits": safe(lambda: count("/search/commits", f"author:{user}")),
        "prs": safe(lambda: count("/search/issues", f"author:{user} type:pr")),
        "issues": safe(lambda: count("/search/issues", f"author:{user} type:issue")),
        "langs": langs,
    }


def demo():
    return {"stars": 12, "repos": 9, "followers": 4, "commits": 321, "prs": 14,
            "issues": 3, "langs": {"JavaScript": 52000, "CSS": 21000, "HTML": 14000,
                                   "GLSL": 6000, "Python": 4000}}


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else str(n)


def stats_svg(user, d):
    rows = [("Total Stars", d["stars"]), ("Total Commits", d["commits"]),
            ("Pull Requests", d["prs"]), ("Issues", d["issues"]),
            ("Public Repos", d["repos"]), ("Followers", d["followers"])]
    out = [
        '<svg width="495" height="195" viewBox="0 0 495 195" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="GitHub stats for {escape(user)}">',
        f'<rect x="0.5" y="0.5" width="494" height="194" rx="8" fill="{BG}" stroke="{BORDER}"/>',
        f'<text x="25" y="35" font-family="Segoe UI, Ubuntu, sans-serif" font-size="18" font-weight="600" '
        f'fill="{TITLE}">{escape(user)}\'s GitHub Stats</text>',
    ]
    for i, (label, value) in enumerate(rows):
        y = 70 + i * 20
        out.append(f'<circle cx="31" cy="{y - 4}" r="3.5" fill="{ACCENT}"/>')
        out.append(f'<text x="45" y="{y}" font-family="Segoe UI, Ubuntu, sans-serif" font-size="14" '
                   f'fill="{MUTED}">{label}:</text>')
        out.append(f'<text x="240" y="{y}" font-family="Segoe UI, Ubuntu, sans-serif" font-size="14" '
                   f'font-weight="600" fill="{TEXT}">{escape(fmt(value))}</text>')
    out.append("</svg>")
    return "\n".join(out)


def langs_svg(d):
    langs = sorted(d["langs"].items(), key=lambda kv: kv[1], reverse=True)[:6]
    total = sum(v for _, v in langs) or 1
    out = [
        '<svg width="300" height="195" viewBox="0 0 300 195" xmlns="http://www.w3.org/2000/svg" role="img" '
        'aria-label="Most used languages">',
        f'<rect x="0.5" y="0.5" width="299" height="194" rx="8" fill="{BG}" stroke="{BORDER}"/>',
        f'<text x="25" y="35" font-family="Segoe UI, Ubuntu, sans-serif" font-size="18" font-weight="600" '
        f'fill="{TITLE}">Most Used Languages</text>',
        '<clipPath id="bar"><rect x="25" y="52" width="250" height="8" rx="4"/></clipPath>',
        '<g clip-path="url(#bar)">',
    ]
    x = 25.0
    colored = []
    for i, (name, size) in enumerate(langs):
        color = LANG_COLORS.get(name, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
        w = 250 * size / total
        out.append(f'<rect x="{x:.2f}" y="52" width="{w:.2f}" height="8" fill="{color}"/>')
        colored.append((name, size, color))
        x += w
    out.append("</g>")
    for i, (name, size, color) in enumerate(colored):
        col, row = divmod(i, 3)
        cx, cy = 25 + col * 130, 90 + row * 28
        out.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{color}"/>')
        out.append(f'<text x="{cx + 17}" y="{cy}" font-family="Segoe UI, Ubuntu, sans-serif" font-size="12" '
                   f'fill="{TEXT}">{escape(name)} <tspan fill="{MUTED}">{100 * size / total:.1f}%</tspan></text>')
    if not colored:
        out.append(f'<text x="25" y="95" font-family="Segoe UI, Ubuntu, sans-serif" font-size="13" '
                   f'fill="{MUTED}">No language data yet</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    args = [a for a in sys.argv[1:] if a != "--demo"]
    outdir = args[0] if args else "dist"
    user = os.environ.get("GH_USER", "s755k")
    data = demo() if "--demo" in sys.argv else collect(user)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(stats_svg(user, data))
    with open(os.path.join(outdir, "top-langs.svg"), "w", encoding="utf-8") as f:
        f.write(langs_svg(data))
    print(f"wrote stats.svg and top-langs.svg to {outdir}")


if __name__ == "__main__":
    main()
