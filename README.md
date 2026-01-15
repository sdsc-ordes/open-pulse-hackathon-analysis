# LauZHack Projects Extractor

Scrapes LauZHack hackathon data (2023-2025) and enriches it with GitHub repository information.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

**1. Scrape hackathon data:**

```bash
python lauzhack_scraper.py
```

Outputs: `data/lauzhack_projects.csv`, `data/lauzhack_projects.json`, `data/lauzhack_hackathons.csv`, `data/lauzhack_hackathons.json`

**2. Enrich with GitHub data:**

```bash
python enrich_github_data.py --token YOUR_GITHUB_TOKEN
```

Outputs: `data/lauzhack_projects_with_github.csv`, `data/github_repos_data.json`

Get your GitHub token: [github.com/settings/tokens](https://github.com/settings/tokens)

## Data Fields

**Projects CSV:**

- Basic: year, name, awards, description, team, link, tags
- GitHub: stars, forks, language, contributors, commit dates, README

**Hackathons CSV:**

- year, url, date, location, schedule

## Files

**`lauzhack_scraper.py`**

- Scrapes LauZHack websites (2023-2025) to extract project information and hackathon metadata
- Outputs: `data/lauzhack_projects.csv`, `data/lauzhack_projects.json`, `data/lauzhack_hackathons.csv`, `data/lauzhack_hackathons.json`

**`github_extractor.py`**

- Helper module with functions to extract GitHub repo data (stars, forks, commits, contributors, README)
- Used by `enrich_github_data.py` (no need to run directly)

**`enrich_github_data.py`**

- Takes the scraped projects and enriches them with GitHub data for all repos
- Outputs: `data/lauzhack_projects_with_github.csv`, `data/github_repos_data.json`
