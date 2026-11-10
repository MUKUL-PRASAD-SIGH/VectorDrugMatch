import pandas as pd

print("Loading dataset")

df = pd.read_csv("data/processed/pubchem_50k.csv")

print("Creating basic features")

# Length of SMILES string (proxy for molecule size)
df["smiles_length"] = df["smiles"].apply(len)

# Count of atoms (very rough approximation)
df["num_C"] = df["smiles"].str.count("C")
df["num_O"] = df["smiles"].str.count("O")
df["num_N"] = df["smiles"].str.count("N")
df["num_S"] = df["smiles"].str.count("S")

print("Saving enriched dataset...")

df.to_csv("data/processed/pubchem_50k_features.csv", index=False)

print("\nDone")
print(df.head())
