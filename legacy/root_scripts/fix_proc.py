import sys

content = open('scripts/preprocess.py', encoding='utf-8').read()
content = content.replace('PROC / "diseases.csv"', 'proc_dir / "diseases.csv"')
content = content.replace('PROC / "disease_features.npy"', 'proc_dir / "disease_features.npy"')
content = content.replace('PROC / "genes.csv"', 'proc_dir / "genes.csv"')
content = content.replace('PROC / "edges.csv"', 'proc_dir / "edges.csv"')
content = content.replace('PROC / "drugs.csv"', 'proc_dir / "drugs.csv"')
content = content.replace('PROC / "drug_features.npy"', 'proc_dir / "drug_features.npy"')
open('scripts/preprocess.py', 'w', encoding='utf-8').write(content)
