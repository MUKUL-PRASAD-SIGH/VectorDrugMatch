"""
src/features/graph.py - Graph-level Feature Engineering

Computes structural features from the knowledge graph:
  - Node degree (per type)
  - Betweenness centrality
  - Optional: Node2Vec embeddings
"""

from typing import Optional

import numpy as np
import pandas as pd

try:
    import networkx as nx
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False


def build_networkx_graph(edges_df: pd.DataFrame) -> "nx.MultiDiGraph":
    """Build a NetworkX multi-directed graph from edges DataFrame.

    Args:
        edges_df: DataFrame with source_id, target_id, relation columns.

    Returns:
        NetworkX MultiDiGraph with edge attributes.
    """
    if not NX_AVAILABLE:
        raise ImportError("NetworkX is required. Install with: pip install networkx")

    G = nx.MultiDiGraph()
    for _, row in edges_df.iterrows():
        G.add_edge(
            str(row["source_id"]),
            str(row["target_id"]),
            relation=row.get("relation", "unknown"),
            source_type=row.get("source_type", "unknown"),
            target_type=row.get("target_type", "unknown"),
        )
    return G


def compute_node_degrees(edges_df: pd.DataFrame) -> pd.DataFrame:
    """Compute in-degree, out-degree, and total degree for each node.

    Args:
        edges_df: DataFrame with source_id and target_id columns.

    Returns:
        DataFrame with columns: node_id, in_degree, out_degree, total_degree.
    """
    out_deg = edges_df["source_id"].value_counts().rename("out_degree")
    in_deg = edges_df["target_id"].value_counts().rename("in_degree")

    all_nodes = set(edges_df["source_id"].astype(str)) | set(edges_df["target_id"].astype(str))
    degree_df = pd.DataFrame({"node_id": list(all_nodes)})
    degree_df = degree_df.set_index("node_id")
    degree_df["out_degree"] = out_deg.reindex(degree_df.index).fillna(0).astype(int)
    degree_df["in_degree"] = in_deg.reindex(degree_df.index).fillna(0).astype(int)
    degree_df["total_degree"] = degree_df["out_degree"] + degree_df["in_degree"]

    return degree_df.reset_index()


def compute_centrality(G: "nx.MultiDiGraph", top_k: int = 1000) -> dict[str, float]:
    """Compute betweenness centrality for a NetworkX graph.

    For very large graphs, samples a subset of nodes for efficiency.

    Args:
        G: NetworkX graph.
        top_k: If graph has more than top_k nodes, use approximate centrality.

    Returns:
        Dictionary mapping node_id → centrality score.
    """
    if not NX_AVAILABLE:
        raise ImportError("NetworkX required.")

    if G.number_of_nodes() > top_k:
        # Use approximate centrality for large graphs
        centrality = nx.betweenness_centrality(G, k=min(top_k, G.number_of_nodes()))
    else:
        centrality = nx.betweenness_centrality(G)

    return centrality


def degree_features_for_nodes(nodes_df: pd.DataFrame, edges_df: pd.DataFrame,
                               id_col: str = "drug_id") -> pd.DataFrame:
    """Add degree features to a node DataFrame.

    Args:
        nodes_df: DataFrame with node IDs.
        edges_df: Edges DataFrame.
        id_col: Column name for node ID in nodes_df.

    Returns:
        nodes_df with added degree columns.
    """
    degree_df = compute_node_degrees(edges_df)
    result = nodes_df.copy()
    degree_lookup = degree_df.set_index("node_id")

    result["degree"] = result[id_col].astype(str).map(
        degree_lookup["total_degree"]
    ).fillna(0).astype(int)

    return result
