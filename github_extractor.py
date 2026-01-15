#!/usr/bin/env python3
"""
GitHub Repository Data Extractor
Extracts comprehensive data from GitHub repositories including:
- Repository metadata (stars, forks, language, description)
- Commit information (first/last commit dates)
- Contributors count
- README content
"""

import re
import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

import requests


@dataclass
class GitHubRepoData:
    """GitHub repository data"""
    owner: str
    repo: str
    stars: int = 0
    forks: int = 0
    language: str = ""
    description: str = ""
    url: str = ""
    created_at: str = ""
    updated_at: str = ""
    first_commit_date: str = ""
    last_commit_date: str = ""
    contributors_count: int = 0
    readme: str = ""


def extract_github_owner_repo(url: str) -> Optional[Tuple[str, str]]:
    """
    Extracts GitHub owner and repo from a GitHub URL.
    Handles formats like:
      https://github.com/owner/repo
      https://github.com/owner/repo/
      https://github.com/owner/repo.git
    """
    match = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git|/)?$", url)
    if match:
        return match.group(1), match.group(2)
    return None


def fetch_complete_repo_data(owner: str, repo: str, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches complete repository data in optimized API calls.

    Makes efficient calls to:
    1. /repos/{owner}/{repo} - Main metadata (stars, forks, language, description, dates)
    2. /repos/{owner}/{repo}/commits - Last commit (first in response)
    3. /repos/{owner}/{repo}/commits - First commit (last page)
    4. /repos/{owner}/{repo}/contributors - Count from pagination header
    5. raw.githubusercontent.com - README content

    Args:
        owner: Repository owner
        repo: Repository name
        token: Optional GitHub API token (increases rate limit from 60 to 5000 requests/hour)

    Returns:
        Dictionary with all repo data or empty dict on error
    """
    headers = {"User-Agent": "LauZHack-Extractor"}
    if token:
        headers["Authorization"] = f"token {token}"

    result = {
        "metadata": {},
        "first_commit_date": "",
        "last_commit_date": "",
        "contributors_count": 0,
        "readme": ""
    }

    # 1. Get main repository metadata (stars, forks, language, description, created_at, updated_at)
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            result["metadata"] = r.json()
        elif r.status_code == 404:
            return {}
        else:
            print(f"  API error {r.status_code} for {owner}/{repo}")
            return {}
    except Exception as e:
        print(f"  Error fetching metadata for {owner}/{repo}: {e}")
        return {}

    # 2. Get last commit date (first result from commits endpoint)
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1"
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200 and r.json():
            result["last_commit_date"] = r.json(
            )[0]["commit"]["author"]["date"]
    except Exception as e:
        print(f"  Error fetching last commit for {owner}/{repo}: {e}")

    # 3. Get first commit date (last page of commits)
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1&sha={result['metadata'].get('default_branch', 'main')}"
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            # Check Link header for last page
            link_header = r.headers.get("Link", "")
            if "last" in link_header:
                # Extract last page URL
                match = re.search(r'<([^>]+)>; rel="last"', link_header)
                if match:
                    last_page_url = match.group(1)
                    r2 = requests.get(
                        last_page_url, headers=headers, timeout=30)
                    if r2.status_code == 200 and r2.json():
                        result["first_commit_date"] = r2.json(
                        )[-1]["commit"]["author"]["date"]
            elif r.json():
                # Only one page of commits
                result["first_commit_date"] = r.json(
                )[0]["commit"]["author"]["date"]
    except Exception as e:
        print(f"  Error fetching first commit for {owner}/{repo}: {e}")

    # 4. Get contributors count (from pagination header)
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/contributors?per_page=1"
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            link_header = r.headers.get("Link", "")
            if "last" in link_header:
                # Extract last page number
                match = re.search(r'page=(\d+)>; rel="last"', link_header)
                if match:
                    result["contributors_count"] = int(match.group(1))
            else:
                result["contributors_count"] = len(r.json())
    except Exception as e:
        print(f"  Error fetching contributors for {owner}/{repo}: {e}")

    # 5. Get README from raw content
    default_branch = result["metadata"].get("default_branch", "main")
    for branch in [default_branch, "main", "master"]:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200:
                result["readme"] = r.text
                break
        except Exception:
            continue

    return result


def extract_github_data(
    repo_url: str,
    token: Optional[str] = None,
    fetch_readme: bool = True,
    verbose: bool = False
) -> Optional[GitHubRepoData]:
    """
    Extracts comprehensive GitHub repository data using optimized API calls.

    Args:
        repo_url: GitHub repository URL
        token: Optional GitHub API token
        fetch_readme: Whether to fetch README content
        verbose: Print progress information

    Returns:
        GitHubRepoData object or None if extraction fails
    """
    parts = extract_github_owner_repo(repo_url)
    if not parts:
        return None

    owner, repo = parts

    if verbose:
        print(f"Extracting GitHub data for {owner}/{repo}...")

    # Fetch all data in optimized calls
    raw_data = fetch_complete_repo_data(owner, repo, token)
    if not raw_data or not raw_data.get("metadata"):
        return None

    metadata = raw_data["metadata"]

    data = GitHubRepoData(
        owner=owner,
        repo=repo,
        stars=metadata.get("stargazers_count", 0),
        forks=metadata.get("forks_count", 0),
        language=metadata.get("language", ""),
        description=metadata.get("description", ""),
        url=metadata.get("html_url", ""),
        created_at=metadata.get("created_at", ""),
        updated_at=metadata.get("updated_at", ""),
        first_commit_date=raw_data.get("first_commit_date", ""),
        last_commit_date=raw_data.get("last_commit_date", ""),
        contributors_count=raw_data.get("contributors_count", 0),
        readme=raw_data.get("readme", "") if fetch_readme else "",
    )

    if verbose:
        print(
            f"  ✓ {data.stars} stars, {data.contributors_count} contributors, last update: {data.last_commit_date}")

    return data


def extract_github_data_batch(
    repo_urls: list,
    token: Optional[str] = None,
    fetch_readme: bool = True,
    delay: float = 0.1,
    verbose: bool = True
) -> Dict[str, GitHubRepoData]:
    """
    Extracts GitHub data for multiple repositories with rate limiting.

    Args:
        repo_urls: List of GitHub repository URLs
        token: Optional GitHub API token
        fetch_readme: Whether to fetch README content
        delay: Delay in seconds between requests
        verbose: Print progress information

    Returns:
        Dictionary mapping repo URL to GitHubRepoData
    """
    results = {}

    for i, url in enumerate(repo_urls, 1):
        if verbose:
            print(f"[{i}/{len(repo_urls)}] Processing {url}...")

        data = extract_github_data(
            url, token=token, fetch_readme=fetch_readme, verbose=False)
        if data:
            results[url] = data

        # Rate limiting
        if i < len(repo_urls):
            time.sleep(delay)

    return results


if __name__ == "__main__":
    # Example usage
    test_url = "https://github.com/torvalds/linux"
    data = extract_github_data(test_url, fetch_readme=False, verbose=True)
    if data:
        print("\nExtracted data:")
        for key, value in asdict(data).items():
            if key == "readme":
                print(
                    f"  {key}: {len(value)} chars" if value else f"  {key}: (empty)")
            else:
                print(f"  {key}: {value}")
