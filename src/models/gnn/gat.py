"""
src/models/gnn/gat.py - Graph Attention Network (GAT) Baseline

Leverages attention mechanisms to weight neighbor importance. 
Wrapped using `to_hetero`.
"""

import torch
import torch.nn.functional as F
from torch_geometric.nn import GATConv, to_hetero
from torch.nn import BatchNorm1d

class GAT(torch.nn.Module):
    def __init__(self, hidden_channels, out_channels, num_layers=2, heads=4):
        super().__init__()
        self.convs = torch.nn.ModuleList()
        self.norms = torch.nn.ModuleList()
        
        # Output of first layer is hidden_channels * heads
        self.convs.append(GATConv((-1, -1), hidden_channels, heads=heads, add_self_loops=False))
        self.norms.append(BatchNorm1d(hidden_channels * heads))
        
        for _ in range(num_layers - 2):
            self.convs.append(GATConv(hidden_channels * heads, hidden_channels, heads=heads, add_self_loops=False))
            self.norms.append(BatchNorm1d(hidden_channels * heads))
            
        if num_layers > 1:
            # Last layer usually averages attention heads (concat=False)
            self.convs.append(GATConv(hidden_channels * heads, out_channels, heads=1, concat=False, add_self_loops=False))
            self.norms.append(BatchNorm1d(out_channels))

        # Decided statically so to_hetero's symbolic tracing never branches on tensor shapes
        widths = [n.num_features for n in self.norms]
        self.residual = [i > 0 and widths[i] == widths[i - 1] for i in range(len(widths))]

    def forward(self, x, edge_index):
        for i, (conv, norm) in enumerate(zip(self.convs, self.norms)):
            x_out = conv(x, edge_index)
            x_out = norm(x_out)
            
            # Residual connection
            if self.residual[i]:
                x_out = x_out + x
                
            x = x_out
            if i < len(self.convs) - 1:
                x = F.elu(x)
                x = F.dropout(x, p=0.2, training=self.training)
        return x

def create_gat_model(metadata, hidden_channels=32, out_channels=64, num_layers=2, heads=4):
    """Factory to create a Hetero-GAT."""
    model = GAT(hidden_channels, out_channels, num_layers, heads)
    return to_hetero(model, metadata, aggr="sum")
