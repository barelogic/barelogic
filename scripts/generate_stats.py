#!/usr/bin/env python3
"""Generate all stats SVGs straight from the GitHub GraphQL API.

Outputs (all self-contained, SMIL-only animation, no third-party loads):
  stats.svg  — contributions in the last year
  streak.svg — current and longest streak
  langs.svg  — top languages by bytes and by repo
  year.svg   — the last year, one character per day (ramp : + # @)
  hd-*.svg   — section headings in this page's own typeface

Usage:
  python scripts/generate_stats.py --user VenkateshR-Karunya --demo
  GITHUB_TOKEN=... python scripts/generate_stats.py --user VenkateshR-Karunya

Language totals cover public repositories only. Nothing is fetched from
anyone else's server at view time.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
import urllib.request

W = 620
BG, FRAME, TXT, DIM, ACCENT, GREEN = (
    "#0d1117", "#21262d", "#e6edf3", "#8b949e", "#58a6ff", "#3fb950",
)
FONT_CSS_TEMPLATE = (
    "@font-face{font-family:'JetBrains Mono';"
    "src:url(data:font/ttf;base64,%s) format('truetype');}"
    "text{font-family:'JetBrains Mono',monospace;}"
)
YEAR_RAMP = [":", "+", "#", "@"]  # quiet to loud


def embed_font(font_path: str, chars: str) -> str:
    if not os.path.exists(font_path):
        return "text{font-family:monospace;}"
    try:
        import io

        data = open(font_path, "rb").read()
        try:
            from fontTools import subset

            font = subset.load_font(font_path, subset.Options())
            ss = subset.Subsetter(subset.Options())
            ss.populate(text=chars)
            ss.subset(font)
            buf = io.BytesIO()
            font.save(buf)
            data = buf.getvalue()
        except Exception:
            pass
        return FONT_CSS_TEMPLATE % base64.b64encode(data).decode()
    except Exception as e:
        print(f"warn: font embed skipped: {e}", file=sys.stderr)
        return "text{font-family:monospace;}"


def frame(title: str, body: str, height: int, css: str, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'viewBox="0 0 {W} {height}" role="img" aria-label="{label}">'
        f"<title>{title}</title><style>{css}</style>"
        f'<rect width="{W}" height="{height}" rx="8" fill="{BG}"/>'
        f"{body}"
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{height - 1}" rx="8" '
        f'fill="none" stroke="{FRAME}"/></svg>\n'
    )


def heading_svg(text: str, css: str) -> str:
    # 620x56 heading bar; lowercase JetBrains Mono with accent rule.
    body = (
        f'<text x="20" y="36" font-size="24" fill="{TXT}" letter-spacing="1">'
        f"{text}</text>"
        f'<rect x="20" y="44" width="48" height="3" fill="{GREEN}">'
        '<animate attributeName="width" from="0" to="48" dur="0.8s" fill="freeze"/>'
        "</rect>"
    )
    return frame(text, body, 56, css, text)


# ---------------------------------------------------------------- data ---

def demo_data():
    today = dt.date.today()
    days = []
    import random

    rnd = random.Random(42)
    for i in range(364, -1, -1):
        d = today - dt.timedelta(days=i)
        # weekday-weighted pseudo activity so streaks look real
        c = rnd.choices([0, 1, 2, 3, 5, 8], weights=[25, 20, 20, 15, 12, 8])[0]
        if d.weekday() >= 5 and rnd.random() < 0.4:
            c = 0
        days.append({"date": d.isoformat(), "count": c})
    months = [0] * 12
    for e in days:
        m = int(e["date"][5:7]) - 1
        months[m] += e["count"]
    return {
        "total": sum(e["count"] for e in days),
        "days": days,
        "months": months,
        "langs_bytes": [
            ("Python", 420000), ("JavaScript", 310000), ("TypeScript", 180000),
            ("HTML", 90000), ("CSS", 70000),
        ],
        "langs_repos": [
            ("Python", 9), ("JavaScript", 7), ("HTML", 5),
            ("CSS", 4), ("Shell", 2),
        ],
    }


def fetch_github(user: str, token: str):
    q = """
    query($login:String!){
      user(login:$login){
        contributionsCollection{
          contributionCalendar{
            totalContributions
            weeks{ contributionDays{ date contributionCount } }
          }
        }
        repositories(first:100, ownerAffiliations:OWNER, privacy:PUBLIC,
                     orderBy:{field:UPDATED_AT,direction:DESC}){
          nodes{ primaryLanguage{ name } languages(first:10, orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name } } } }
        }
      }
    }"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": q, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    u = data["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    days = [{"date": d["date"], "count": d["contributionCount"]} for d in days][-365:]
    months = [0] * 12
    for e in days:
        months[int(e["date"][5:7]) - 1] += e["count"]
    b: dict[str, int] = {}
    rc: dict[str, int] = {}
    for repo in u["repositories"]["nodes"]:
        seen = set()
        for e in repo["languages"]["edges"]:
            b[e["node"]["name"]] = b.get(e["node"]["name"], 0) + e["size"]
            seen.add(e["node"]["name"])
        for name in seen:
            rc[name] = rc.get(name, 0) + 1
    top = lambda d, n=5: sorted(d.items(), key=lambda kv: -kv[1])[:n]
    return {"total": cal["totalContributions"], "days": days, "months": months,
            "langs_bytes": top(b) or demo_data()["langs_bytes"],
            "langs_repos": top(rc) or demo_data()["langs_repos"]}


def streaks(days) -> tuple[int, int]:
    cur = mx = run = 0
    for e in days:
        run = run + 1 if e["count"] > 0 else 0
        mx = max(mx, run)
    for e in reversed(days):
        if e["count"] > 0:
            cur += 1
        else:
            break
    # trailing today-with-no-commits-yet shouldn't kill the streak display
    if cur == 0 and len(days) > 1 and days[-2]["count"] > 0:
        for e in reversed(days[:-1]):
            if e["count"] > 0:
                cur += 1
            else:
                break
    return cur, mx


# -------------------------------------------------------------- builders ---

def stats_svg(d, css) -> str:
    ms = d["months"]
    mx = max(ms) or 1
    bars = ""
    bw = 34
    x0 = 30
    base = 118
    for i, v in enumerate(ms):
        h = max(4, round(v / mx * 72))
        x = x0 + i * 44
        bars += (
            f'<rect x="{x}" y="{base - h}" width="{bw}" height="{h}" rx="3" '
            f'fill="{GREEN}" opacity="0.9"><title>{v} contributions</title>'
            f'<animate attributeName="height" from="0" to="{h}" dur="0.7s" '
            f'begin="{i * 0.05:.2f}s" fill="freeze"/>'
            f'<animate attributeName="y" from="{base}" to="{base - h}" dur="0.7s" '
            f'begin="{i * 0.05:.2f}s" fill="freeze"/></rect>'
        )
    body = (
        f'<text x="20" y="30" font-size="15" fill="{TXT}">'
        f"Contributions in the last year: {d['total']}</text>"
        f"{bars}"
        f'<text x="20" y="140" font-size="11" fill="{DIM}">Jan … Dec · public only</text>'
    )
    return frame("stats", body, 156, css, "Contributions in the last year")


def streak_svg(d, css) -> str:
    cur, mx = streaks(d["days"])

    def cell(x, v, lab, delay):
        return (
            f'<text x="{x}" y="62" font-size="34" fill="{TXT}">{v}'
            f'<animate attributeName="opacity" from="0" to="1" dur="0.7s" '
            f'begin="{delay}s" fill="freeze"/></text>'
            f'<text x="{x}" y="86" font-size="12" fill="{DIM}">{lab}</text>'
        )

    body = (
        cell(24, f"{cur} day{'s' if cur != 1 else ''}", "current streak", "0.1")
        + cell(300, f"{mx} day{'s' if mx != 1 else ''}", "longest streak", "0.3")
        + f'<rect x="270" y="28" width="1" height="64" fill="{FRAME}"/>'
    )
    return frame("streak", body, 108, css, "Current and longest streak")


def langs_svg(d, css) -> str:
    def rows(items, x, scale, fmt, color):
        s = ""
        y = 52
        for i, (name, v) in enumerate(items):
            w = max(8, round(v / scale * 220))
            s += (
                f'<text x="{x}" y="{y}" font-size="12" fill="{TXT}">{name}</text>'
                f'<text x="{x + 235}" y="{y}" font-size="12" fill="{DIM}">{fmt(v)}</text>'
                f'<rect x="{x}" y="{y + 6}" width="{w}" height="8" rx="4" fill="{color}">'
                f'<animate attributeName="width" from="0" to="{w}" dur="0.7s" '
                f'begin="{i * 0.07:.2f}s" fill="freeze"/></rect>'
            )
            y += 34
        return s, y

    sb = max(v for _, v in d["langs_bytes"])
    sr = max(v for _, v in d["langs_repos"])
    left, _ = rows(d["langs_bytes"], 24, sb, lambda v: f"{v // 1000}k", GREEN)
    right, _ = rows(d["langs_repos"], 330, sr, lambda v: f"{v} repos", ACCENT)
    body = (
        f'<text x="24" y="28" font-size="12" fill="{DIM}">by bytes</text>'
        f'<text x="330" y="28" font-size="12" fill="{DIM}">by repo</text>'
        f"{left}{right}"
        f'<rect x="305" y="16" width="1" height="200" fill="{FRAME}"/>'
    )
    return frame("langs", body, 232, css, "Top languages by bytes and by repo")


def year_svg(d, css) -> str:
    days = d["days"][-371:]  # 53 cols x 7 rows
    while len(days) < 371:
        days = [{"date": "", "count": 0}] + days
    def ch(c: int) -> str:
        if c <= 0:
            return YEAR_RAMP[0]
        if c <= 2:
            return YEAR_RAMP[1]
        if c <= 5:
            return YEAR_RAMP[2]
        return YEAR_RAMP[3]

    fs = 13
    cw = fs * 0.6
    x0, y0 = 30, 44
    cells = ""
    k = 0
    for col in range(53):
        for row in range(7):
            e = days[col * 7 + row]
            x = x0 + col * (cw + 3.4)
            y = y0 + row * (fs + 3)
            cells += (
                f'<text x="{x:.1f}" y="{y}" font-size="{fs}" '
                f'fill="{GREEN if e["count"] else DIM}" '
                f'opacity="{0.35 if not e["count"] else 0.95}">'
                f"{ch(e['count'])}"
                f'<title>{e["date"] or "—"}: {e["count"]}</title></text>'
            )
            k += 1
    body = (
        f'<text x="20" y="26" font-size="13" fill="{TXT}">'
        f"The last year, one character per day</text>"
        f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" '
        f'dur="1.2s" fill="freeze"/>{cells}</g>'
        f'<text x="20" y="{y0 + 7 * (fs + 3) + 16}" font-size="11" '
        f'fill="{DIM}">: + # @ — quiet to loud</text>'
    )
    h = int(y0 + 7 * (fs + 3) + 32)
    return frame("year", body, h, css, "The last year, one character per day")


# ------------------------------------------------------------------ main ---

HEADINGS = {
    "hd-about.svg": "about",
    "hd-stack.svg": "stack",
    "hd-projects.svg": "projects",
    "hd-stats.svg": "stats",
    "hd-about-this-page.svg": "about this page",
}

FONT_PATH = "scripts/fonts/JetBrainsMono-Regular.ttf"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("PROFILE_USER", "VenkateshR-Karunya"))
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if args.demo or not token:
        data = demo_data()
        print("using demo data (no token or --demo)", file=sys.stderr)
    else:
        try:
            data = fetch_github(args.user, token)
        except Exception as e:
            print(f"warn: API failed ({e}); falling back to demo", file=sys.stderr)
            data = demo_data()

    css = embed_font(FONT_PATH, "abcdefghijklmnopqrstuvwxyz0123456789.:+#@ /—·()")
    outs = {
        "stats.svg": stats_svg(data, css),
        "streak.svg": streak_svg(data, css),
        "langs.svg": langs_svg(data, css),
        "year.svg": year_svg(data, css),
    }
    for name, text in HEADINGS.items():
        outs[name] = heading_svg(text, css)
    for name, svg in outs.items():
        with open(name, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
