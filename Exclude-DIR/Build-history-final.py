import pandas as pd
import numpy as np
import time
import sys

def main():
    print("=" * 60)
    print("  History Final — 10-Year Rate Change & Impact Analysis")
    print("=" * 60)

    # Load data
    try:
        df = pd.read_csv('history.csv', dtype=str)
    except FileNotFoundError:
        print("\nERROR: history.csv not found in current directory.")
        sys.exit(1)

    print(f"\nLoaded history.csv: {len(df)} rows, {len(df.columns)} columns")

    # Discover years from columns
    year_set = set()
    for col in df.columns:
        if col.endswith('_Deaths') or col.endswith('_Population'):
            parts = col.split('_')
            if parts[0].isdigit():
                year_set.add(int(parts[0]))
    all_years = sorted(year_set)
    print(f"Years in data: {all_years[0]}-{all_years[-1]} ({len(all_years)} years)")

    # Dynamically pick the last 10 years
    last_10 = all_years[-10:]
    period_a_years = last_10[:5]
    period_b_years = last_10[5:]
    analysis_label = f"{last_10[0]} through {last_10[-1]}"

    print(f"\nAnalysis window: {analysis_label}")
    print(f"  Period A: {period_a_years[0]}-{period_a_years[-1]}")
    print(f"  Period B: {period_b_years[0]}-{period_b_years[-1]}")

    # Add analysis period label to every row
    df['Analysis_Period'] = analysis_label

    # Convert Order to numeric for filtering
    order_num = pd.to_numeric(df['Order'], errors='coerce')

    # Pre-compute rate for each year in the 10-year window
    print("\nCalculating rates...")
    for y in last_10:
        d_vals = pd.to_numeric(df[f'{y}_Deaths'].str.replace(',', '', regex=False), errors='coerce')
        p_vals = pd.to_numeric(df[f'{y}_Population'].str.replace(',', '', regex=False), errors='coerce')
        df[f'_rate_{y}'] = np.where((p_vals > 0) & d_vals.notna() & p_vals.notna(),
                                     (d_vals / p_vals) * 100000, np.nan)

    # Period A and B averages (require all 5 years present)
    rate_a_cols = [f'_rate_{y}' for y in period_a_years]
    rate_b_cols = [f'_rate_{y}' for y in period_b_years]

    valid_a_count = df[rate_a_cols].notna().sum(axis=1)
    valid_b_count = df[rate_b_cols].notna().sum(axis=1)
    has_full_data = (valid_a_count == 5) & (valid_b_count == 5)

    avg_a = df[rate_a_cols].mean(axis=1)
    avg_b = df[rate_b_cols].mean(axis=1)
    rate_change = avg_b - avg_a
    rate_change_pct = np.where(avg_a > 0, (rate_change / avg_a) * 100, np.nan)

    df['Avg_Rate_PeriodA'] = np.where(has_full_data, avg_a.round(2), np.nan)
    df['Avg_Rate_PeriodB'] = np.where(has_full_data, avg_b.round(2), np.nan)
    df['Rate_Change'] = np.where(has_full_data, rate_change.round(2), np.nan)
    df['Rate_Change_Pct'] = np.where(has_full_data, np.round(rate_change_pct, 2), np.nan)

    # --- US IMPACT CALCULATION ---
    print("Calculating US impact...")

    # Average Period B population for weighting
    pop_b_cols = [f'{y}_Population' for y in period_b_years]
    avg_pop_b = df[pop_b_cols].apply(
        lambda c: pd.to_numeric(c.str.replace(',', '', regex=False), errors='coerce')
    ).mean(axis=1)

    # Only counties (order < 998) with full data
    county_mask = (order_num < 998) & has_full_data

    # Weighted contribution: county rate change * county pop share
    county_pop = avg_pop_b.where(county_mask, 0)
    total_county_pop = county_pop.sum()
    county_rate_change = pd.to_numeric(df['Rate_Change'], errors='coerce').fillna(0)

    weighted_change = np.where(county_mask,
                               county_rate_change * (county_pop / total_county_pop),
                               0)

    total_abs_movement = np.abs(weighted_change[county_mask]).sum()

    impact_pct = np.where(county_mask & (total_abs_movement > 0),
                          (weighted_change / total_abs_movement) * 100,
                          np.nan)
    df['US_Impact_Pct'] = np.round(impact_pct, 4)

    # --- RANKINGS ---
    df['Top_10y_Changes'] = np.nan
    df['Top_10y_Impacts'] = np.nan

    # Work with county-only subset
    counties_idx = df.index[county_mask]
    county_changes = pd.to_numeric(df.loc[counties_idx, 'Rate_Change'], errors='coerce')
    county_impacts = pd.to_numeric(df.loc[counties_idx, 'US_Impact_Pct'], errors='coerce')

    # Rate change rankings
    sorted_by_change = county_changes.sort_values(ascending=False)
    top_10_up = sorted_by_change.head(10)
    top_10_down = sorted_by_change.tail(10).iloc[::-1]

    for rank, idx in enumerate(top_10_up.index, 1):
        df.at[idx, 'Top_10y_Changes'] = rank
    for rank, idx in enumerate(top_10_down.index, 1):
        df.at[idx, 'Top_10y_Changes'] = -rank

    # Impact rankings
    sorted_by_impact = county_impacts.sort_values(ascending=False)
    top_10_impact_up = sorted_by_impact.head(10)
    top_10_impact_down = sorted_by_impact.tail(10).iloc[::-1]

    for rank, idx in enumerate(top_10_impact_up.index, 1):
        df.at[idx, 'Top_10y_Impacts'] = rank
    for rank, idx in enumerate(top_10_impact_down.index, 1):
        df.at[idx, 'Top_10y_Impacts'] = -rank

    # --- SUMMARY ---
    full_count = county_mask.sum()
    gap_count = ((order_num < 998) & ~has_full_data).sum()

    print(f"\n{'_' * 50}")
    print(f"  Counties with full 10-year data: {full_count}")
    print(f"  Counties excluded (gaps):        {gap_count}")
    print(f"{'_' * 50}")

    # Show top 10 rate changes
    print(f"\n  TOP 10 RATE INCREASES ({analysis_label}):")
    for rank in range(1, 11):
        row = df[df['Top_10y_Changes'] == rank]
        if len(row):
            r = row.iloc[0]
            print(f"    #{rank:>3d}  {r['Full_Name']:<35s}  {float(r['Rate_Change']):>+8.1f} per 100K ({float(r['Rate_Change_Pct']):>+6.1f}%)")

    print(f"\n  TOP 10 RATE DECREASES ({analysis_label}):")
    for rank in range(-1, -11, -1):
        row = df[df['Top_10y_Changes'] == rank]
        if len(row):
            r = row.iloc[0]
            print(f"    #{rank:>3d}  {r['Full_Name']:<35s}  {float(r['Rate_Change']):>+8.1f} per 100K ({float(r['Rate_Change_Pct']):>+6.1f}%)")

    print(f"\n  TOP 10 US IMPACT — PUSHING RATE UP:")
    for rank in range(1, 11):
        row = df[df['Top_10y_Impacts'] == rank]
        if len(row):
            r = row.iloc[0]
            print(f"    #{rank:>3d}  {r['Full_Name']:<35s}  Impact: {float(r['US_Impact_Pct']):>+8.4f}%")

    print(f"\n  TOP 10 US IMPACT — PUSHING RATE DOWN:")
    for rank in range(-1, -11, -1):
        row = df[df['Top_10y_Impacts'] == rank]
        if len(row):
            r = row.iloc[0]
            print(f"    #{rank:>3d}  {r['Full_Name']:<35s}  Impact: {float(r['US_Impact_Pct']):>+8.4f}%")

    print(f"\n{'_' * 50}")

    # US row summary for context
    us_rows = df[order_num == 999]
    if len(us_rows):
        us = us_rows.iloc[0]
        if not pd.isna(us['Avg_Rate_PeriodA']):
            print(f"\n  US Rate: {float(us['Avg_Rate_PeriodA']):.1f} (Period A) -> {float(us['Avg_Rate_PeriodB']):.1f} (Period B)")
            print(f"  US Change: {float(us['Rate_Change']):+.1f} per 100K ({float(us['Rate_Change_Pct']):+.1f}%)")

    # Drop internal columns
    drop_cols = [c for c in df.columns if c.startswith('_')]
    df = df.drop(columns=drop_cols)

    # Convert ranking columns to int where present, blank otherwise
    for col in ['Top_10y_Changes', 'Top_10y_Impacts']:
        df[col] = df[col].apply(lambda x: '' if pd.isna(x) else str(int(x)))

    # Convert NaN to empty string for the calculated columns
    for col in ['Avg_Rate_PeriodA', 'Avg_Rate_PeriodB', 'Rate_Change', 'Rate_Change_Pct', 'US_Impact_Pct']:
        df[col] = df[col].apply(lambda x: '' if pd.isna(x) or str(x) == 'nan' else x)

    # Pause for review
    print(f"\n  Output will be saved in 10 seconds...")
    print(f"  Review the summary above for any issues.")
    time.sleep(10)

    # Save
    df.to_csv('history-final.csv', index=False)
    print(f"\n  SAVED: history-final.csv ({len(df)} rows, {len(df.columns)} columns)")
    print("=" * 60)

if __name__ == "__main__":
    main()