"""
src/data/graph_builder.py - Build PyTorch Geometric HeteroData from processed CSVs

Converts the processed CSV files into a heterogeneous graph suitable for
GNN training with PyTorch Geometric.

Node Types: Drug, Gene, Disease
Edge Types: CtD, CpD, CbG, CdG, CuG, DaG, DuG, DdG, GiG, GrG, DaG_disgenet

Usage:
    from src.data.graph_builder import build_hetero_data
    data = build_hetero_data("data/processed")
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    import torch
    from torch_geometric.data import HeteroData
    import torch_geometric.transforms as T
    PYG_AVAILABLE = True
except ImportError:
    PYG_AVAILABLE = False


# Mapping from Hetionet source_type strings to our canonical node types
NODE_TYPE_MAP = {
    "Compound": "drug",
    "Gene": "gene",
    "Disease": "disease",
    "Anatomy": "anatomy",
    "Biological Process": "biological_process",
    "Cellular Component": "cellular_component",
    "Molecular Function": "molecular_function",
    "Pathway": "pathway",
    "Pharmacologic Class": "pharmacologic_class",
    "Side Effect": "side_effect",
    "Symptom": "symptom",
}

# Edge type mapping: metaedge → (src_type, relation_name, dst_type)
EDGE_TYPE_MAP = {
    "CtD": ("drug", "treats", "disease"),
    "CpD": ("drug", "palliates", "disease"),
    "CbG": ("drug", "binds", "gene"),
    "CdG": ("drug", "downregulates", "gene"),
    "CuG": ("drug", "upregulates", "gene"),
    "DaG": ("disease", "associates", "gene"),
    "DuG": ("disease", "upregulates_gene", "gene"),
    "DdG": ("disease", "downregulates_gene", "gene"),
    "GiG": ("gene", "interacts", "gene"),
    "GrG": ("gene", "regulates", "gene"),
    "DaG_disgenet": ("gene", "disgenet_associates", "disease"),
}


def build_hetero_data(processed_dir: str | Path,
                       include_features: bool = True) -> "HeteroData":
    """Build a PyTorch Geometric HeteroData object from processed CSVs.

    Args:
        processed_dir: Path to the data/processed/ directory.
        include_features: If True, load drug_features.npy as node features.

    Returns:
        HeteroData object with typed nodes and edges.

    Raises:
        ImportError: If PyTorch Geometric is not installed.
        FileNotFoundError: If required CSV files are missing.
    """
    if not PYG_AVAILABLE:
        raise ImportError(
            "PyTorch Geometric is required. Install with:\n"
            "  pip install torch-geometric"
        )

    proc = Path(processed_dir)
    data = HeteroData()

    # ------------------------------------------------------------------
    # Load node DataFrames
    # ------------------------------------------------------------------
    drugs_df = pd.read_csv(proc / "drugs.csv")
    diseases_df = pd.read_csv(proc / "diseases.csv")
    genes_df = pd.read_csv(proc / "genes.csv")
    edges_df = pd.read_csv(proc / "edges.csv")

    # Create node ID → index mappings
    drug_ids = drugs_df["drug_id"].astype(str).tolist()
    disease_ids = diseases_df["disease_id"].astype(str).tolist()
    gene_ids = genes_df["gene_id"].astype(str).tolist()

    drug_id2idx = {nid: i for i, nid in enumerate(drug_ids)}
    disease_id2idx = {nid: i for i, nid in enumerate(disease_ids)}
    gene_id2idx = {nid: i for i, nid in enumerate(gene_ids)}

    id2idx_map = {
        "drug": drug_id2idx,
        "disease": disease_id2idx,
        "gene": gene_id2idx,
    }

    # ------------------------------------------------------------------
    # Set node features
    # ------------------------------------------------------------------
    # Drug features: 3246-dim (Morgan + MACCS + Scaffolds + Descriptors)
    fp_path = proc / "drug_features.npy"
    if include_features and fp_path.exists():
        drug_fp = np.load(fp_path)
        data["drug"].x = torch.tensor(drug_fp, dtype=torch.float32)
    else:
        print("  [WARNING] drug_features.npy not found. Using empty feature matrix.")
        data["drug"].x = torch.zeros((len(drug_ids), 3246), dtype=torch.float32)

    data["drug"].num_nodes = len(drug_ids)

    # Compute node degrees to use as basic topological features
    disease_degrees = edges_df[edges_df["target_type"] == "Disease"]["target_id"].value_counts().to_dict()
    disease_degrees.update(edges_df[edges_df["source_type"] == "Disease"]["source_id"].value_counts().to_dict())
    
    gene_degrees = edges_df[edges_df["target_type"] == "Gene"]["target_id"].value_counts().to_dict()
    gene_degrees.update(edges_df[edges_df["source_type"] == "Gene"]["source_id"].value_counts().to_dict())

    # Disease features: [is_ntd, daly_rate, degree]
    # In a real publication, add sentence-transformers or MeSH embeddings here.
    disease_feats = []
    for _, row in diseases_df.iterrows():
        did = str(row["disease_id"])
        disease_feats.append([
            float(row.get("is_ntd", 0)),
            float(row.get("daly_rate", 0.0)),
            float(disease_degrees.get(did, 0.0)),
        ])
    data["disease"].x = torch.tensor(disease_feats, dtype=torch.float32)
    data["disease"].num_nodes = len(disease_ids)

    # Gene features: topological degree representation
    # Removed memory-bloating Identity matrix (torch.eye). 
    # Use torch.nn.Embedding inside GNN architectures for node-specific learning.
    gene_feats = []
    for gid in gene_ids:
        gene_feats.append([float(gene_degrees.get(gid, 0.0))])
    data["gene"].x = torch.tensor(gene_feats, dtype=torch.float32)
    data["gene"].num_nodes = len(gene_ids)

    # ------------------------------------------------------------------
    # Build edge indices (per relation type)
    # ------------------------------------------------------------------
    skipped_edges = 0
    edge_counts = {}

    for relation, edge_spec in EDGE_TYPE_MAP.items():
        src_type, rel_name, dst_type = edge_spec

        # Filter edges for this relation
        rel_edges = edges_df[edges_df["relation"] == relation]
        if len(rel_edges) == 0:
            continue

        src_indices = []
        dst_indices = []
        src_map = id2idx_map.get(src_type, {})
        dst_map = id2idx_map.get(dst_type, {})

        for _, row in rel_edges.iterrows():
            src_id = str(row["source_id"])
            dst_id = str(row["target_id"])

            if src_id in src_map and dst_id in dst_map:
                src_indices.append(src_map[src_id])
                dst_indices.append(dst_map[dst_id])
            else:
                skipped_edges += 1

        if src_indices:
            edge_index = torch.tensor([src_indices, dst_indices], dtype=torch.long)
            data[src_type, rel_name, dst_type].edge_index = edge_index
            edge_counts[f"({src_type}, {rel_name}, {dst_type})"] = len(src_indices)

    # Add Reverse Edges
    # This automatically adds (disease, rev_treats, drug), etc.
    # Essential for bidirectional message passing in Heterogeneous GNNs.
    data = T.ToUndirected()(data)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'=' * 50}")
    print("HeteroData Graph Summary")
    print(f"{'=' * 50}")
    print(f"  Drug nodes:    {data['drug'].num_nodes:,}")
    print(f"  Disease nodes: {data['disease'].num_nodes:,}")
    print(f"  Gene nodes:    {data['gene'].num_nodes:,}")
    print(f"  Edge types:    {len(data.edge_types)}")
    for etype in data.edge_types:
        print(f"    {etype}: {data[etype].edge_index.size(1):,}")
    if skipped_edges > 0:
        print(f"  [WARNING] Skipped edges (missing node IDs): {skipped_edges:,}")
    print(f"{'=' * 50}")

    return data


def get_positive_edge_index(data: "HeteroData") -> Optional["torch.Tensor"]:
    """Extract the CtD (treats) edge index as positive labels for link prediction.

    Returns:
        Edge index tensor of shape (2, N) or None if no CtD edges exist.
    """
    try:
        return data["drug", "treats", "disease"].edge_index
    except (KeyError, AttributeError):
        return None
