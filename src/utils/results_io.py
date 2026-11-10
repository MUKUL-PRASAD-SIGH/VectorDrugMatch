"""Small helper so per-model runs (needed to resume interrupted experiments) do not overwrite each other's rows in a comparison CSV."""
from pathlib import Path

import pandas as pd


def merge_rows(csv_path, new_rows: pd.DataFrame, key: str = "name") -> pd.DataFrame:
    """Write `new_rows` into csv_path, replacing existing rows with the same `key` and keeping all others (column union, no value invented)."""
    csv_path = Path(csv_path)
    if csv_path.exists() and key in new_rows.columns:
        old = pd.read_csv(csv_path)
        if key in old.columns:
            old = old[~old[key].isin(set(new_rows[key]))]
            new_rows = pd.concat([old, new_rows], ignore_index=True, sort=False)
    new_rows.to_csv(csv_path, index=False)
    return new_rows
