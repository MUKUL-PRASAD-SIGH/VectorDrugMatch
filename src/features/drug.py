"""
src/features/drug.py - Drug Feature Engineering using RDKit

Converts SMILES strings into numerical feature vectors.
Supports toggling different feature families for ablation studies:
  - Morgan Fingerprints (radius=2, 2048-bit)
  - MACCS Keys (167-bit)
  - RDKit continuous descriptors (MW, LogP, TPSA, HBD, HBA, rotatable bonds)
  - Murcko Scaffold Fingerprint (Morgan FP of scaffold, 1024-bit)
  - Avalon Fingerprint (1024-bit)
  - ECFP (Morgan Fingerprint, radius=3, 2048-bit)
  - FCFP (Feature Morgan Fingerprint, radius=3, 2048-bit)

Continuous features are normalized via RobustScaler.
"""

from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import numpy as np
import pandas as pd

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors, DataStructs, MACCSkeys
    from rdkit.Chem.Scaffolds import MurckoScaffold
    from rdkit.Chem import BRICS
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

try:
    from rdkit.Avalon import pyAvalonTools
    AVALON_AVAILABLE = True
except ImportError:
    AVALON_AVAILABLE = False

try:
    from sklearn.preprocessing import RobustScaler
    from joblib import Parallel, delayed
    ML_TOOLS_AVAILABLE = True
except ImportError:
    ML_TOOLS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Core feature extraction
# ---------------------------------------------------------------------------

def compute_all_features(smiles: str, config_flags: dict) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
    """Compute molecular features based on config flags."""
    if not RDKIT_AVAILABLE:
        return None, {}
        
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None, {}

    feature_parts = []
    
    # 1. Standard Morgan FP (radius 2)
    if config_flags.get("use_morgan", True):
        morgan = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
        feature_parts.append(np.array(morgan, dtype=np.float32))
        
    # 2. MACCS Keys
    if config_flags.get("use_maccs", False):
        maccs = MACCSkeys.GenMACCSKeys(mol)
        feature_parts.append(np.array(maccs, dtype=np.float32))
        
    # 3. Scaffold Morgan FP
    if config_flags.get("use_scaffold", False):
        try:
            scaffold_mol = MurckoScaffold.GetScaffoldForMol(mol)
            if scaffold_mol and scaffold_mol.GetNumAtoms() > 0:
                scaff = AllChem.GetMorganFingerprintAsBitVect(scaffold_mol, radius=2, nBits=1024)
                feature_parts.append(np.array(scaff, dtype=np.float32))
            else:
                feature_parts.append(np.zeros(1024, dtype=np.float32))
        except Exception:
            feature_parts.append(np.zeros(1024, dtype=np.float32))
            
    # 4. Avalon FP
    if config_flags.get("use_avalon", False):
        if AVALON_AVAILABLE:
            avalon = pyAvalonTools.GetAvalonFP(mol, nBits=1024)
            feature_parts.append(np.array(avalon, dtype=np.float32))
        else:
            # Graceful fallback if Avalon requested but not installed
            feature_parts.append(np.zeros(1024, dtype=np.float32))
            
    # 5. ECFP3
    if config_flags.get("use_ecfp3", False):
        ecfp3 = AllChem.GetMorganFingerprintAsBitVect(mol, radius=3, nBits=2048)
        feature_parts.append(np.array(ecfp3, dtype=np.float32))
        
    # 6. FCFP3
    if config_flags.get("use_fcfp3", False):
        fcfp3 = AllChem.GetMorganFingerprintAsBitVect(mol, radius=3, nBits=2048, useFeatures=True)
        feature_parts.append(np.array(fcfp3, dtype=np.float32))
        
    if not feature_parts:
        # Fallback if everything is disabled
        feature_parts.append(np.zeros(2048, dtype=np.float32))
        
    bit_vector = np.concatenate(feature_parts)
    
    # 7. Descriptors
    descriptors = {}
    if config_flags.get("use_descriptors", False):
        try:
            brics_count = len(BRICS.BRICSDecompose(mol))
        except Exception:
            brics_count = 0
            
        descriptors = {
            "mw": Descriptors.MolWt(mol),
            "logp": Descriptors.MolLogP(mol),
            "tpsa": Descriptors.TPSA(mol),
            "hbd": int(Descriptors.NumHDonors(mol)),
            "hba": int(Descriptors.NumHAcceptors(mol)),
            "rotatable_bonds": int(Descriptors.NumRotatableBonds(mol)),
            "brics_fragments": brics_count
        }

    return bit_vector, descriptors


# ---------------------------------------------------------------------------
# Batch processing & Normalization
# ---------------------------------------------------------------------------

def _process_single(smi: str, config_flags: dict, empty_len: int) -> Tuple[np.ndarray, Dict[str, Any]]:
    if not smi or smi == "nan":
        return np.zeros(empty_len, dtype=np.float32), {}
        
    vec, desc = compute_all_features(smi, config_flags)
    if vec is not None:
        return vec, desc
    
    return np.zeros(empty_len, dtype=np.float32), {}


def featurize_drugs_df(drugs_df: pd.DataFrame, config_flags: dict,
                       smiles_col: str = "smiles", n_jobs: int = -1) -> Tuple[pd.DataFrame, np.ndarray]:
    if not RDKIT_AVAILABLE or not ML_TOOLS_AVAILABLE:
        raise ImportError("RDKit and scikit-learn/joblib required for featurization.")

    # Calculate expected bit vector length
    empty_len = 0
    if config_flags.get("use_morgan", True): empty_len += 2048
    if config_flags.get("use_maccs", False): empty_len += 167
    if config_flags.get("use_scaffold", False): empty_len += 1024
    if config_flags.get("use_avalon", False): empty_len += 1024
    if config_flags.get("use_ecfp3", False): empty_len += 2048
    if config_flags.get("use_fcfp3", False): empty_len += 2048
    
    if empty_len == 0:
        empty_len = 2048 # Fallback

    if config_flags.get("use_avalon", False) and not AVALON_AVAILABLE:
        print("    [WARNING] Warning: Avalon fingerprints requested but rdkit.Avalon is not installed. Using zero-vectors.")

    smiles_list = drugs_df[smiles_col].astype(str).tolist()
    print(f"    Extracting requested chemical features for {len(smiles_list)} drugs in parallel...")
    
    results = Parallel(n_jobs=n_jobs)(
        delayed(_process_single)(smi, config_flags, empty_len) for smi in smiles_list
    )
    
    bit_vectors = []
    desc_rows = []
    
    for vec, desc in results:
        bit_vectors.append(vec)
        if desc and config_flags.get("use_descriptors", False):
            desc_rows.append(desc)
        elif config_flags.get("use_descriptors", False):
            desc_rows.append({
                "mw": 0.0, "logp": 0.0, "tpsa": 0.0,
                "hbd": 0, "hba": 0, "rotatable_bonds": 0, "brics_fragments": 0
            })
            
    bit_matrix = np.array(bit_vectors, dtype=np.float32)
    result_df = drugs_df.copy()
    
    if config_flags.get("use_descriptors", False):
        desc_df = pd.DataFrame(desc_rows)
        scale_cols = ["mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "brics_fragments"]
        
        print(f"    Normalizing {len(scale_cols)} continuous descriptors...")
        scaler = RobustScaler()
        scaled_descs = scaler.fit_transform(desc_df[scale_cols].fillna(0))
        
        for col in scale_cols:
            result_df[col] = desc_df[col].values
            
        final_matrix = np.concatenate([bit_matrix, scaled_descs.astype(np.float32)], axis=1)
    else:
        final_matrix = bit_matrix
        
    print(f"    [OK] Final drug feature matrix shape: {final_matrix.shape}")
    return result_df, final_matrix
