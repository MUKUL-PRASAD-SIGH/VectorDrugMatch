"""
src/models/gnn/gcn.py - Numerically stable heterogeneous GCN.

Degree features are log1p-scaled inside the GCN encoder.
Other model architectures and the underlying dataset remain unchanged.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GraphConv, to_hetero


class GCN(nn.Module):
    def __init__(self, hidden_channels, out_channels, num_layers=2):
        super().__init__()

        if num_layers < 1:
            raise ValueError("num_layers must be at least 1")

        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()
        self.dropout = nn.Dropout(p=0.2)

        self.convs.append(
            GraphConv(-1, hidden_channels, aggr="mean")
        )
        self.norms.append(nn.BatchNorm1d(hidden_channels))

        for _ in range(num_layers - 2):
            self.convs.append(
                GraphConv(hidden_channels, hidden_channels, aggr="mean")
            )
            self.norms.append(nn.BatchNorm1d(hidden_channels))

        if num_layers > 1:
            self.convs.append(
                GraphConv(hidden_channels, out_channels, aggr="mean")
            )
            self.norms.append(nn.BatchNorm1d(out_channels))

        widths = [norm.num_features for norm in self.norms]
        self.residual = [
            i > 0 and widths[i] == widths[i - 1]
            for i in range(len(widths))
        ]

    def forward(self, x, edge_index):
        for i, (conv, norm) in enumerate(zip(self.convs, self.norms)):
            x_out = conv(x, edge_index)
            x_out = norm(x_out)

            if self.residual[i]:
                x_out = x_out + x

            x = x_out

            if i < len(self.convs) - 1:
                x = F.relu(x)
                x = self.dropout(x)

        return x


class StableHeteroGCN(nn.Module):
    """GCN with GCN-specific feature scaling and mean relation aggregation."""

    def __init__(self, metadata, hidden_channels, out_channels, num_layers):
        super().__init__()

        base_model = GCN(
            hidden_channels=hidden_channels,
            out_channels=out_channels,
            num_layers=num_layers,
        )

        self.encoder = to_hetero(
            base_model,
            metadata,
            aggr="mean",
        )

    def forward(self, x_dict, edge_index_dict):
        # Copy the dictionary; do not mutate the original graph features.
        x_dict = dict(x_dict)

        if "disease" in x_dict and x_dict["disease"].size(1) > 2:
            disease_x = x_dict["disease"]
            scaled_degree = torch.log1p(
                disease_x[:, 2:3].clamp(min=0)
            )
            x_dict["disease"] = torch.cat(
                [disease_x[:, :2], scaled_degree, disease_x[:, 3:]],
                dim=1,
            )

        if "gene" in x_dict and x_dict["gene"].size(1) > 0:
            gene_x = x_dict["gene"]
            scaled_degree = torch.log1p(
                gene_x[:, :1].clamp(min=0)
            )
            x_dict["gene"] = torch.cat(
                [scaled_degree, gene_x[:, 1:]],
                dim=1,
            )

        return self.encoder(x_dict, edge_index_dict)


def create_gcn_model(metadata, hidden_channels=64, out_channels=64, num_layers=2):
    """Factory for the numerically stable heterogeneous GCN."""
    return StableHeteroGCN(
        metadata,
        hidden_channels=hidden_channels,
        out_channels=out_channels,
        num_layers=num_layers,
    )
