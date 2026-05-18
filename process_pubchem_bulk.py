import pandas as pd

print("Loading ONLY first 50k rows")

df = pd.read_csv(
    "data/raw/CID-SMILES",
    sep="\t",
    header=None,
    names=["cid", "smiles"],
    nrows=50000   # KEY LINE (fast)
)

print(f"Loaded entries: {len(df)}")

df = df.dropna()
df = df.drop_duplicates()

df.to_csv("data/processed/pubchem_50k.csv", index=False)

print(" Saved 50k dataset")
