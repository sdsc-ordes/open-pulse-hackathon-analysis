#!/usr/bin/env python3
import re
import csv
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# Optional fallback (only used if requests fetch is blocked or JS-rendered)
try:
    from playwright.sync_api import sync_playwright  # type: ignore
    HAVE_PLAYWRIGHT = True
except Exception:
    HAVE_PLAYWRIGHT = False


PROJECT_URLS = {
    2025: "https://2025.lauzhack.com/projects",
    2024: "https://2024.lauzhack.com/projects",
    2023: "https://2023.lauzhack.com/projects",
}

HOME_URLS = {
    2025: "https://2025.lauzhack.com/",
    2024: "https://2024.lauzhack.com/",
    2023: "https://2023.lauzhack.com/",
}


@dataclass
class Project:
    year: int
    name: str
    awards: str
    description: str
    team: str
    link: str
    tags: List[str]


@dataclass
class HackathonInfo:
    year: int
    url: str
    date_line: str
    location_line: str
    # [{"day": "Saturday", "time": "8:00-9:30", "item": "Check in and breakfast"}, ...]
    schedule: List[Dict[str, str]]


def fetch_html_requests(url: str, timeout: int = 30) -> Tuple[int, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    return r.status_code, r.text


def fetch_html_playwright(url: str, timeout_ms: int = 45000) -> str:
    if not HAVE_PLAYWRIGHT:
        raise RuntimeError(
            "Playwright not installed. Install with:\n"
            "  pip install playwright\n"
            "  playwright install"
        )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        # Handle lazy loading/infinite scroll
        for _ in range(8):
            page.mouse.wheel(0, 2500)
            time.sleep(0.35)
        html = page.content()
        browser.close()
        return html


def get_html(url: str) -> str:
    status, html = fetch_html_requests(url)
    # Some sites return 200 but with an empty shell; length guard helps.
    if status >= 400 or len(html.strip()) < 3000:
        return fetch_html_playwright(url)
    return html


def _clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def extract_challenge_tags_from_page(soup: BeautifulSoup) -> List[str]:
    """
    Attempts to extract the tag vocabulary from the "Challenge" filter row on /projects.
    Works best on the static pages (e.g., 2023), and is harmless if not present.
    """
    # Strategy:
    # 1) Look for any element whose visible text contains "Challenge"
    # 2) From its parent container, collect short label-like texts (buttons/links/spans)
    # 3) Filter obvious noise
    challenge_node = None
    for node in soup.find_all(string=re.compile(r"\bChallenge\b", re.I)):
        parent = node.parent
        if parent:
            challenge_node = parent
            break

    if not challenge_node:
        return []

    container = challenge_node.parent if challenge_node.parent else challenge_node

    labels: List[str] = []
    for el in container.find_all(["button", "a", "span", "div", "p"], recursive=True):
        t = _clean_spaces(el.get_text(" ", strip=True))
        if not t:
            continue
        # Filter out big paragraphs
        if len(t) > 40:
            continue
        labels.append(t)

    # The row often looks like: "Challenge any Bristol Myers Squibb AWS ..."
    joined = " ".join(labels)
    joined = re.sub(r"\bChallenge\b", " ", joined, flags=re.I)
    joined = re.sub(r"\bany\b", " ", joined, flags=re.I)
    joined = _clean_spaces(joined)

    # Known multi-word tags that appear on the site (add more if you discover them)
    multi = [
        "Bristol Myers Squibb",
        "EPFL Sustainability",
        "Open Systems",
    ]

    found: List[str] = []
    tmp = joined
    for m in multi:
        if m in tmp:
            found.append(m)
            tmp = tmp.replace(m, " ")

    # Remaining are usually single tokens like AWS, SBB, Swisscom, AXA, Logitech, Swissquote, S2S, etc.
    tokens = [t for t in re.split(r"\s{1,}", _clean_spaces(tmp)) if t]
    # Remove duplicates while preserving order
    seen = set()
    for x in found + tokens:
        x = _clean_spaces(x)
        if not x:
            continue
        if x.lower() in {"challenge", "any"}:
            continue
        if x.lower() in seen:
            continue
        seen.add(x.lower())
        found.append(x)

    return found


def detect_project_tags(text_blob: str, tag_vocab: List[str]) -> List[str]:
    """
    Uses the tag vocabulary extracted from the page and searches for mentions in the project's
    title/awards/description region.
    """
    if not tag_vocab:
        return []
    hay = " " + (text_blob or "") + " "
    hay_lower = hay.lower()

    tags: List[str] = []
    for tag in tag_vocab:
        # Whole-word-ish match, but allow spaces in tag names
        pat = r"\b" + re.escape(tag.lower()) + r"\b"
        if re.search(pat, hay_lower):
            tags.append(tag)

    return tags


def parse_projects_generic(year: int, html: str) -> List[Project]:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup.body or soup

    tag_vocab = extract_challenge_tags_from_page(soup)

    # Identify project boundaries by anchor text "Link"
    link_anchors = main.find_all("a", string=re.compile(r"^\s*Link\s*$", re.I))
    hrefs: List[str] = []
    for i, a in enumerate(link_anchors):
        hrefs.append(a.get("href", "").strip())
        a.replace_with(f" [[LINK_{i}]] ")

    text = main.get_text("\n", strip=True)

    if not hrefs:
        # fallback: buttons like "GitHub", "Repo", etc.
        candidates = []
        for a in main.find_all("a", href=True):
            t = (a.get_text() or "").strip().lower()
            if t in {"link", "demo", "repository", "repo", "github", "gitlab"}:
                candidates.append(a)
        if candidates:
            hrefs = [a["href"].strip() for a in candidates]
            for i, a in enumerate(candidates):
                a.replace_with(f" [[LINK_{i}]] ")
            text = main.get_text("\n", strip=True)

    parts = re.split(r"\[\[LINK_(\d+)\]\]", text)
    blocks: Dict[int, str] = {}
    for j in range(1, len(parts), 2):
        idx = int(parts[j])
        block = parts[j - 1]
        blocks[idx] = block

    projects: List[Project] = []

    for i, href in enumerate(hrefs):
        block = blocks.get(i, "")
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue

        lines_tail = lines[-12:]

        # Team line heuristic
        team_idx = None
        for k in range(len(lines_tail) - 1, -1, -1):
            ln = lines_tail[k]
            if ("," in ln or " and " in ln.lower()) and len(ln) <= 180:
                team_idx = k
                break
        if team_idx is None:
            team_idx = len(lines_tail) - 1
        team = lines_tail[team_idx]

        # Description lines above team
        desc_lines: List[str] = []
        k = team_idx - 1
        while k >= 0:
            ln = lines_tail[k]
            if ln.lower() in {"projects"}:
                break
            if len(ln.split()) == 1 and ln[0].isupper() and len(ln) <= 20:
                break
            if "," in ln and len(ln) <= 120:
                break
            desc_lines.insert(0, ln)
            if sum(len(x) for x in desc_lines) > 320:
                break
            k -= 1
        description = _clean_spaces(" ".join(desc_lines)) if desc_lines else ""

        # Title line is usually the line right before desc start
        title_idx = k
        if title_idx < 0:
            title_idx = max(0, team_idx - 1)

        title_line = lines_tail[title_idx] if 0 <= title_idx < len(
            lines_tail) else lines_tail[0]
        title_line = _clean_spaces(title_line)

        # Split title into name and awards
        name = title_line
        awards = ""
        m = re.split(r"\s{2,}", title_line)
        if len(m) >= 2:
            name = m[0].strip()
            awards = _clean_spaces(" ".join(m[1:]))
        else:
            kw = re.search(
                r"\b(1st|2nd|3rd)\b|\bplace\b|\bwinner\b|\bprize\b", title_line, re.I)
            if kw:
                pos = kw.start()
                name = title_line[:pos].strip().rstrip(",")
                awards = title_line[pos:].strip()

        # Resolve relative links
        if href.startswith("/"):
            href = f"https://{year}.lauzhack.com{href}"

        # Tags: search in title + awards + description region
        tag_haystack = " ".join([name, awards, description])
        tags = detect_project_tags(tag_haystack, tag_vocab)

        if name.lower() == "projects":
            continue

        projects.append(
            Project(
                year=year,
                name=name,
                awards=awards,
                description=description,
                team=team,
                link=href,
                tags=tags,
            )
        )

    # De-duplicate by (year, name, link)
    seen = set()
    uniq: List[Project] = []
    for p in projects:
        key = (p.year, p.name.lower(), p.link)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)

    return uniq


def parse_hackathon_home(year: int, url: str, html: str) -> HackathonInfo:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup.body or soup
    lines = [ln.strip() for ln in main.get_text(
        "\n", strip=True).splitlines() if ln.strip()]

    # Date line heuristic: first line containing a Month name
    month_re = re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
        re.I,
    )
    date_line = ""
    for ln in lines[:40]:
        if month_re.search(ln):
            date_line = ln
            break

    # Location line heuristic: mentions EPFL, Lausanne, Switzerland, campus
    location_line = ""
    for ln in lines[:80]:
        if re.search(r"\b(EPFL|Lausanne|Switzerland|campus)\b", ln, re.I):
            location_line = ln
            break

    # Schedule parsing: expects blocks like
    # "## Saturday" then "8:00-9:30 ..." lines, then "## Sunday" etc.
    schedule: List[Dict[str, str]] = []
    current_day: Optional[str] = None
    time_item_re = re.compile(r"^(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})\s+(.*)$")

    for ln in lines:
        # Day heading
        if ln.lower() in {"saturday", "sunday"}:
            current_day = ln
            continue
        # Sometimes headings come as "## Saturday" but text extraction already strips hashes
        if ln.lower().endswith("day") and ln.lower() in {"saturday", "sunday"}:
            current_day = ln
            continue

        m = time_item_re.match(ln)
        if m and current_day:
            schedule.append(
                {"day": current_day, "time": m.group(1), "item": m.group(2).strip()})

    return HackathonInfo(
        year=year,
        url=url,
        date_line=date_line,
        location_line=location_line,
        schedule=schedule,
    )


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_projects_csv(path: str, projects: List[Project]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["year", "name", "awards", "description",
                        "team", "link", "tags", "readme"],
        )
        w.writeheader()
        for p in projects:
            row = asdict(p)
            row["tags"] = "|".join(p.tags)
            w.writerow(row)


def save_hackathons_csv(path: str, infos: List[HackathonInfo]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["year", "url", "date_line",
                        "location_line", "schedule_json"],
        )
        w.writeheader()
        for info in infos:
            w.writerow(
                {
                    "year": info.year,
                    "url": info.url,
                    "date_line": info.date_line,
                    "location_line": info.location_line,
                    "schedule_json": json.dumps(info.schedule, ensure_ascii=False),
                }
            )


def main() -> None:
    all_projects: List[Project] = []
    hackathons: List[HackathonInfo] = []

    # Projects
    for year, url in PROJECT_URLS.items():
        print(f"Fetching projects {year}: {url}")
        html = get_html(url)
        projects = parse_projects_generic(year, html)
        print(f"  found {len(projects)} projects")
        all_projects.extend(projects)

    # Hackathon metadata
    for year, url in HOME_URLS.items():
        print(f"Fetching home {year}: {url}")
        html = get_html(url)
        info = parse_hackathon_home(year, url, html)
        hackathons.append(info)

    # Outputs
    save_json("data/lauzhack_projects.json", [asdict(p) for p in all_projects])
    save_projects_csv("data/lauzhack_projects.csv", all_projects)

    save_json("data/lauzhack_hackathons.json", [asdict(h) for h in hackathons])
    save_hackathons_csv("data/lauzhack_hackathons.csv", hackathons)

    print("\nWrote:")
    print("  data/lauzhack_projects.json")
    print("  data/lauzhack_projects.csv")
    print("  data/lauzhack_hackathons.json")
    print("  data/lauzhack_hackathons.csv")
    print("\nTo enrich with GitHub data, run:")
    print("  python enrich_github_data.py [--token YOUR_GITHUB_TOKEN]")


if __name__ == "__main__":
    main()
