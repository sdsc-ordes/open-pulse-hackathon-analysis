#!/usr/bin/env python3
"""
Enriches the projects CSV with GitHub repository data.

Usage:
    python enrich_github_data.py [--token YOUR_GITHUB_TOKEN]
"""

import csv
import json
import sys
from pathlib import Path
from dataclasses import asdict

import pandas as pd

from github_extractor import extract_github_data_batch


def main():
    # Check if token is provided
    token = None
    if "--token" in sys.argv:
        idx = sys.argv.index("--token")
        if idx + 1 < len(sys.argv):
            token = sys.argv[idx + 1]

    # Load existing projects
    projects_csv = "data/lauzhack_projects.csv"
    if not Path(projects_csv).exists():
        print(f"Error: {projects_csv} not found")
        return

    df = pd.read_csv(projects_csv)

    # Filter GitHub projects
    github_urls = df[df["link"].str.contains(
        "github.com", na=False)]["link"].unique().tolist()
    print(f"Found {len(github_urls)} unique GitHub repositories")

    # Extract GitHub data
    print("\nExtracting GitHub repository data...")
    github_data = extract_github_data_batch(
        github_urls,
        token=token,
        fetch_readme=True,  # Get README content
        delay=0.1,
        verbose=True
    )

    print(f"\nSuccessfully extracted data for {len(github_data)} repositories")

    # Create GitHub enriched data file
    github_output = "data/github_repos_data.json"
    with open(github_output, "w", encoding="utf-8") as f:
        data_to_save = {
            url: asdict(repo_data) for url, repo_data in github_data.items()
        }
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)

    print(f"Saved GitHub data to {github_output}")

    # Create enriched projects CSV with GitHub data
    enriched_output = "data/lauzhack_projects_with_github.csv"

    with open(enriched_output, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "year", "name", "awards", "description", "team", "link", "tags",
            "github_stars", "github_forks", "github_language", "github_created_at",
            "github_updated_at", "github_first_commit", "github_last_commit",
            "github_contributors", "github_readme"
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for _, row in df.iterrows():
            repo_data = github_data.get(row["link"])

            output_row = {
                "year": row["year"],
                "name": row["name"],
                "awards": row["awards"],
                "description": row["description"],
                "team": row["team"],
                "link": row["link"],
                "tags": row["tags"],
                "github_stars": repo_data.stars if repo_data else "",
                "github_forks": repo_data.forks if repo_data else "",
                "github_language": repo_data.language if repo_data else "",
                "github_created_at": repo_data.created_at if repo_data else "",
                "github_updated_at": repo_data.updated_at if repo_data else "",
                "github_first_commit": repo_data.first_commit_date if repo_data else "",
                "github_last_commit": repo_data.last_commit_date if repo_data else "",
                "github_contributors": repo_data.contributors_count if repo_data else "",
                "github_readme": repo_data.readme if repo_data else "",
            }
            w.writerow(output_row)

    print(f"Saved enriched projects to {enriched_output}")

    # Print summary
    print("\n" + "="*60)
    print("ENRICHMENT SUMMARY")
    print("="*60)
    enriched_df = pd.read_csv(enriched_output)
    print(f"Total projects in enriched CSV: {len(enriched_df)}")
    print(
        f"Projects with GitHub data: {enriched_df['github_stars'].notna().sum()}")
    print(f"\nTop 10 starred repositories:")
    top_starred = enriched_df[enriched_df['github_stars'].notna()].nlargest(10, 'github_stars')[
        ['name', 'github_stars', 'github_contributors']
    ]
    print(top_starred.to_string(index=False))


if __name__ == "__main__":
    main()
