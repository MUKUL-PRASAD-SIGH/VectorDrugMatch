"""
src/models/gnn/hgt.py - Heterogeneous Graph Transformer (HGT) ★ FINAL MODEL ★

HGT explicitly models both node types and edge types using multi-head attention.
It is the most advanced model in the progression, designed specifically for
scale and extreme heterogeneity (like the biomedical KG).
"""

import torch
import torch.nn.functional as F
from torch_geometric.nn import HGTConv, Linear

class HGT(torch.nn.Module):
    def __init__(self, metadata, hidden_channels, out_channels, num_layers=2, heads=4):
        super().__init__()
        
        self.node_types = metadata[0]
        
        # 1. Linear projection for all node features to a common hidden_channels
        self.lin_dict = torch.nn.ModuleDict()
        for node_type in self.node_types:
            self.lin_dict[node_type] = Linear(-1, hidden_channels)
            
        # 2. HGT Convolutional Layers and LayerNorms
        self.convs = torch.nn.ModuleList()
        self.norms = torch.nn.ModuleList()
        for _ in range(num_layers):
            self.convs.append(
                HGTConv(hidden_channels, hidden_channels, metadata, heads)
            )
            norm_dict = torch.nn.ModuleDict()
            for node_type in self.node_types:
                norm_dict[node_type] = torch.nn.LayerNorm(hidden_channels)
            self.norms.append(norm_dict)
            
        # 3. Output projection
        self.out_dict = torch.nn.ModuleDict()
        for node_type in self.node_types:
            self.out_dict[node_type] = Linear(hidden_channels, out_channels)

    def forward(self, x_dict, edge_index_dict):
        # Initial linear projection to common dimension
        out_dict = {
            node_type: F.gelu(self.lin_dict[node_type](x)) 
            for node_type, x in x_dict.items()
        }
        
        # HGT layers with Residual and LayerNorm
        for conv, norm_dict in zip(self.convs, self.norms):
            x_out = conv(out_dict, edge_index_dict)
            
            # Apply LayerNorm and Residual per node type
            for node_type in self.node_types:
                x = x_out[node_type]
                x = norm_dict[node_type](x)
                x_out[node_type] = x + out_dict[node_type] # Residual
                
            out_dict = x_out
            
        # Output projection
        final_dict = {
            node_type: self.out_dict[node_type](x)
            for node_type, x in out_dict.items()
        }
        
        return final_dict

def create_hgt_model(metadata, hidden_channels=64, out_channels=64, num_layers=2, heads=4):
    """Factory to create the Heterogeneous Graph Transformer."""
    return HGT(metadata, hidden_channels, out_channels, num_layers, heads)
