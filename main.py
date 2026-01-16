#!/usr/bin/env python3
"""
Main data merger and analysis script.
Combines all scraped and enriched data into a comprehensive dataset.
"""

import pandas as pd
import json
from pathlib import Path


def load_data():
    """Load all available datasets."""
    print("Loading data...")

    # Load projects with GitHub data (main dataset)
    projects_df = pd.read_csv("data/lauzhack_projects_with_github.csv")
    print(f"  ✓ Loaded {len(projects_df)} projects with GitHub data")

    # Load hackathon metadata
    hackathons_df = pd.read_csv("data/lauzhack_hackathons.csv")
    print(f"  ✓ Loaded {len(hackathons_df)} hackathons metadata")

    return projects_df, hackathons_df


def merge_data(projects_df, hackathons_df):
    """Merge projects with hackathon metadata."""
    print("\nMerging datasets...")

    # Merge on year
    merged_df = projects_df.merge(
        hackathons_df,
        on="year",
        how="left",
        validate="many_to_one"
    )

    print(
        f"  ✓ Merged dataset has {len(merged_df)} rows and {len(merged_df.columns)} columns")

    return merged_df


def analyze_data(df):
    """Generate basic statistics and insights."""
    print("\n" + "="*60)
    print("DATA ANALYSIS")
    print("="*60)

    # Basic stats
    print(f"\nTotal projects: {len(df)}")
    print(f"Years covered: {sorted(df['year'].unique().tolist())}")

    # GitHub stats
    github_projects = df[df['github_stars'].notna()]
    print(f"\nProjects with GitHub data: {len(github_projects)}")

    if len(github_projects) > 0:
        print(f"Total stars: {int(github_projects['github_stars'].sum())}")
        print(f"Total forks: {int(github_projects['github_forks'].sum())}")
        print(
            f"Total contributors: {int(github_projects['github_contributors'].sum())}")

        # Top languages
        print("\nTop 5 programming languages:")
        lang_counts = df['github_language'].value_counts().head(5)
        for lang, count in lang_counts.items():
            print(f"  {lang}: {count} projects")

        # Top starred projects
        print("\nTop 5 starred projects:")
        top_projects = github_projects.nlargest(5, 'github_stars')[
            ['name', 'year', 'github_stars', 'github_language']
        ]
        for _, row in top_projects.iterrows():
            print(
                f"  {row['name']} ({row['year']}): {int(row['github_stars'])} stars - {row['github_language']}")

    # Projects by year
    print("\nProjects per year:")
    year_counts = df['year'].value_counts().sort_index()
    for year, count in year_counts.items():
        print(f"  {year}: {count} projects")

    # Awards distribution
    awarded = df[df['awards'].notna() & (df['awards'] != '')]
    print(f"\nProjects with awards: {len(awarded)}")


def save_merged_data(df):
    """Save the merged dataset."""
    output_file = "data/lauzhack_complete_dataset.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✓ Saved complete dataset to {output_file}")

    # Also save as JSON
    json_file = "data/lauzhack_complete_dataset.json"
    df.to_json(json_file, orient='records', indent=2)
    print(f"✓ Saved JSON version to {json_file}")


def main():
    """Main execution flow."""
    # print("="*60)
    # print("LAUZHACK DATA MERGER")
    # print("="*60)

    # # Ensure data directory exists
    # Path("data").mkdir(exist_ok=True)
    # 
    # # Load data
    # projects_df, hackathons_df = load_data()
    # 
    # # Merge datasets
    # merged_df = merge_data(projects_df, hackathons_df)
    # 
    # # Save merged data
    # save_merged_data(merged_df)

    # print("\n" + "="*60)
    # print("✓ Complete! All data merged and saved.")
    # print("="*60)

    complete_df = pd.read_csv("data/lauzhack_complete_dataset.csv")

    # Calculate contribution span
    complete_df['contribution_span'] = (pd.to_datetime(complete_df['github_last_commit']) - pd.to_datetime(complete_df['github_first_commit'])).dt.days
    print(f"Contribution span calculated for {len(complete_df)} projects")

    print(complete_df[complete_df['contribution_span']>=30].value_counts('year'))

    # analyze_data(complete_df)

    print(complete_df.columns)




if __name__ == "__main__":
    main()
