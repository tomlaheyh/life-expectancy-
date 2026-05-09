import pandas as pd
import os
import glob
import re
import traceback
from io import StringIO

def clean_and_save_individual(filepath):
    """
    Cleans a single CDC file, saves a '_cleaned.csv' version, 
    and returns the dataframe for merging.
    """
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)
    name_part, _ = os.path.splitext(filename)
    
    # Skip files already cleaned or the master output itself
    if name_part.endswith('_cleaned') or "MASTER" in name_part:
        return None

    df = None
    try:
        # STRATEGY 1: Try reading as a true Excel file
        if ext in ['.xlsx', '.xls']:
            try:
                # Try xlrd for old .xls, openpyxl for .xlsx
                engine = 'xlrd' if ext == '.xls' else 'openpyxl'
                df = pd.read_excel(filepath, engine=engine)
            except Exception:
                # STRATEGY 2: Fallback for "Fake" Excel files (actually TSVs)
                with open(filepath, 'r', encoding='latin1') as f:
                    lines = f.readlines()
                
                stop_idx = len(lines)
                for i, line in enumerate(lines):
                    if line.startswith('"---"') or line.startswith('Notes') or (i > 10 and line.strip() == ''):
                        stop_idx = i
                        break
                
                valid_data = "".join(lines[:stop_idx])
                df = pd.read_csv(StringIO(valid_data), sep='\t', quotechar='"', dtype=str)
        
        # STRATEGY 3: Standard Text/CSV files
        else:
            with open(filepath, 'r', encoding='latin1') as f:
                lines = f.readlines()
            
            stop_idx = len(lines)
            for i, line in enumerate(lines):
                if line.startswith('"---"') or line.startswith('Notes') or (i > 10 and line.strip() == ''):
                    stop_idx = i
                    break
            
            valid_data = "".join(lines[:stop_idx])
            df = pd.read_csv(StringIO(valid_data), sep='\t', quotechar='"', dtype=str)

        if df is None or df.empty:
            print(f"!!! WARNING: {filename} appeared to be empty or unreadable.")
            return None

        # Standardize Columns
        col_map = {
            'County': 'County_Name', 
            'County Code': 'County_Code', 
            'Deaths': 'Deaths', 
            'Population': 'Population'
        }
        
        new_cols = {}
        for col in df.columns:
            for key, val in col_map.items():
                if key.lower() in str(col).lower():
                    new_cols[col] = val
        
        df = df.rename(columns=new_cols)

        # Extract Year if missing
        if 'Year' not in df.columns:
            year_match = re.search(r'(\d{4})', filename)
            df['Year'] = year_match.group(1) if year_match else 'Unknown'

        # Filter to core columns
        keep_cols = ['County_Code', 'County_Name', 'Year', 'Deaths', 'Population']
        available_cols = [c for c in keep_cols if c in df.columns]
        
        if 'County_Code' not in available_cols:
            print(f"!!! ERROR: {filename} is missing 'County Code'. Columns found: {df.columns.tolist()}")
            return None

        df = df[available_cols]

        # Clean numeric strings
        for col in ['Deaths', 'Population']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('"', '').str.strip()

        # Save individual cleaned file
        output_name = f"{name_part}_cleaned.csv"
        df.to_csv(output_name, index=False)
        print(f"Successfully processed: {filename} -> {output_name}")
            
        return df

    except Exception:
        print(f"\n--- CRITICAL ERROR IN FILE: {filename} ---")
        traceback.print_exc()
        print("-" * 40 + "\n")
        return None

def process_directory():
    print("Starting processing of CDC files with Excel-to-TSV fallback...\n")
    
    all_files = [f for f in glob.glob("*.*") if f.lower().endswith(('.csv', '.txt', '.xls', '.xlsx'))]
    dataframes = []

    for f in all_files:
        processed_df = clean_and_save_individual(f)
        if processed_df is not None:
            dataframes.append(processed_df)

    if not dataframes:
        print("\nResult: No files were successfully merged.")
    else:
        master_df = pd.concat(dataframes, ignore_index=True)
        
        # Create the master pivot
        pivot_df = master_df.pivot_table(
            index=['County_Code', 'County_Name'],
            columns='Year',
            values=['Deaths', 'Population'],
            aggfunc='first'
        )

        # Flatten columns and handle NaN
        pivot_df.columns = [f"{year}_{metric}" for metric, year in pivot_df.columns]
        pivot_df = pivot_df.reset_index()
        
        cols = ['County_Code', 'County_Name']
        year_cols = sorted([c for c in pivot_df.columns if c not in cols], 
                           key=lambda x: (x.split('_')[0], x.split('_')[1]))
        
        final_output = pivot_df[cols + year_cols]
        final_output.to_csv('MASTER_COUNTY_PIVOT.csv', index=False)
        print(f"\nSUCCESS: Created 'MASTER_COUNTY_PIVOT.csv' with {len(final_output)} rows.")

    print("\n" + "="*50)
    input("Processing complete. Review any errors above and press ENTER to exit.")

if __name__ == "__main__":
    process_directory()