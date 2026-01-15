import pandas as pd

def merge_dataframes(df1, df2, key):
    merged_df = df1.merge(df2, on=key, how="left", validate="many_to_one")
    return merged_df 

def main():
    merged_df = merge_dataframes(
        pd.read_csv("lauzhack_projects.csv"),
        pd.read_csv("lauzhack_hackathons.csv"),
        "year"
    )
    merged_df.to_csv("lauzhack_projects_enriched.csv", index=False)
    print("Merged data saved to lauzhack_projects_enriched.csv")

if __name__ == "__main__":
    main()