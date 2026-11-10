"""
src/models/gnn/base.py - Shared link-prediction wrapper (GNN encoder + MLP edge scorer)
"""

import torch
import torch.nn.functional as F


class LinkPredictor(torch.nn.Module):
    """Simple MLP to predict edge probability from node embeddings."""
    def __init__(self, in_channels, hidden_channels):
        super().__init__()
        # Concat approach: in_channels * 2 -> hidden_channels -> 1
        self.lin1 = torch.nn.Linear(in_channels * 2, hidden_channels)
        self.lin2 = torch.nn.Linear(hidden_channels, 1)

    def forward(self, z_src, z_dst, edge_label_index):
        # Gather embeddings for source and destination nodes of the edges
        z_src_edges = z_src[edge_label_index[0]]
        z_dst_edges = z_dst[edge_label_index[1]]
        
        # Concatenate and pass through MLP
        z = torch.cat([z_src_edges, z_dst_edges], dim=-1)
        z = F.relu(self.lin1(z))
        z = self.lin2(z).squeeze(-1)
        return torch.sigmoid(z)


class GNNLinkPredictionModel(torch.nn.Module):
    """Wrapper that combines a GNN and a LinkPredictor."""
    def __init__(self, gnn, in_channels, hidden_channels):
        super().__init__()
        self.gnn = gnn
        self.predictor = LinkPredictor(in_channels, hidden_channels)
        
    def forward(self, x_dict, edge_index_dict, edge_label_index):
        # 1. Get node embeddings from GNN
        z_dict = self.gnn(x_dict, edge_index_dict)
        
        # 2. Predict links for the specific relation (drug-treats-disease)
        z_src = z_dict['drug']
        z_dst = z_dict['disease']
        
        return self.predictor(z_src, z_dst, edge_label_index)
