"""
src/models/gnn/gcn.py - Graph Convolutional Network (GCN) Baseline

A standard GCN wrapped for heterogeneous graphs using PyG's `to_hetero`.
"""

import torch
import torch.nn.functional as F
from torch_geometric.nn import GraphConv, to_hetero
from torch.nn import BatchNorm1d

class GCN(torch.nn.Module):
    def __init__(self, hidden_channels, out_channels, num_layers=2):
        super().__init__()
        self.convs = torch.nn.ModuleList()
        self.norms = torch.nn.ModuleList()
        
        self.convs.append(GraphConv(-1, hidden_channels))
        self.norms.append(BatchNorm1d(hidden_channels))
        
        for _ in range(num_layers - 2):
            self.convs.append(GraphConv(hidden_channels, hidden_channels))
            self.norms.append(BatchNorm1d(hidden_channels))
            
        if num_layers > 1:
            self.convs.append(GraphConv(hidden_channels, out_channels))
            self.norms.append(BatchNorm1d(out_channels))

    def forward(self, x, edge_index):
        for i, (conv, norm) in enumerate(zip(self.convs, self.norms)):
            x_out = conv(x, edge_index)
            x_out = norm(x_out)
            
            # Residual connection
            if i > 0 and x_out.size(-1) == x.size(-1):
                x_out = x_out + x
                
            x = x_out
            if i < len(self.convs) - 1:
                x = F.relu(x)
                x = F.dropout(x, p=0.2, training=self.training)
        return x

def create_gcn_model(metadata, hidden_channels=64, out_channels=64, num_layers=2):
    """Factory to create a Hetero-GCN."""
    model = GCN(hidden_channels, out_channels, num_layers)
    # Convert the homogeneous GCN to a heterogeneous model
    return to_hetero(model, metadata, aggr="sum")
