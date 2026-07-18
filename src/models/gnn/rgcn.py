"""
src/models/gnn/rgcn.py - Relational Graph Convolutional Network (RGCN)

Designed specifically for multi-relational graphs. Uses PyG's RGCNConv.
Because RGCN operates natively on typed edges (via an edge_type tensor),
we convert the HeteroData edge format to a homogeneous graph with edge types
internally, or simply use `to_hetero` on a custom multi-relational setup.

For simplicity and consistency in PyG 2.x, using `to_hetero` on a GCN with 
different edge relation handlers is functionally similar. However, we'll implement 
a native HeteroConv approach for RGCN to explicitly show relation awareness.
"""

import torch
import torch.nn.functional as F
from torch_geometric.nn import RGCNConv
from torch.nn import LayerNorm

class RGCN(torch.nn.Module):
    def __init__(self, metadata, hidden_channels, out_channels, num_layers=2):
        super().__init__()
        self.node_types, self.edge_types = metadata
        self.num_relations = len(self.edge_types)
        
        self.convs = torch.nn.ModuleList()
        self.norms = torch.nn.ModuleList()
        
        for i in range(num_layers):
            in_dim = -1 if i == 0 else hidden_channels
            out_dim = hidden_channels if i < num_layers - 1 else out_channels
            
            self.convs.append(RGCNConv(in_dim, out_dim, num_relations=self.num_relations))
            self.norms.append(LayerNorm(out_dim))

    def forward(self, x_dict, edge_index_dict):
        # 1. Convert Heterogeneous x_dict and edge_index_dict to Homogeneous format
        node_offsets = {}
        curr_offset = 0
        x_list = []
        for node_type in self.node_types:
            x = x_dict[node_type]
            node_offsets[node_type] = curr_offset
            curr_offset += x.size(0)
            x_list.append(x)
        
        x_homo = torch.cat(x_list, dim=0)
        
        edge_index_list = []
        edge_type_list = []
        for i, edge_type_tuple in enumerate(self.edge_types):
            src, rel, dst = edge_type_tuple
            edge_index = edge_index_dict.get(edge_type_tuple)
            if edge_index is not None and edge_index.size(1) > 0:
                edge_index_offset = edge_index.clone()
                edge_index_offset[0] += node_offsets[src]
                edge_index_offset[1] += node_offsets[dst]
                edge_index_list.append(edge_index_offset)
                edge_type_list.append(torch.full((edge_index.size(1),), i, dtype=torch.long, device=x_homo.device))
                
        if len(edge_index_list) > 0:
            edge_index_homo = torch.cat(edge_index_list, dim=1)
            edge_type_homo = torch.cat(edge_type_list, dim=0)
        else:
            edge_index_homo = torch.empty((2, 0), dtype=torch.long, device=x_homo.device)
            edge_type_homo = torch.empty((0,), dtype=torch.long, device=x_homo.device)

        # 2. Native RGCN Forward Pass
        for i, (conv, norm) in enumerate(zip(self.convs, self.norms)):
            x_out = conv(x_homo, edge_index_homo, edge_type_homo)
            x_out = norm(x_out)
            
            # Residual Connection (skip on first layer because of dim mismatch)
            if i > 0 and x_out.size(-1) == x_homo.size(-1):
                x_out = x_out + x_homo
                
            x_homo = x_out
            
            if i < len(self.convs) - 1:
                x_homo = F.relu(x_homo)
                x_homo = F.dropout(x_homo, p=0.2, training=self.training)

        # 3. Convert Homogeneous output back to x_dict
        out_dict = {}
        for node_type in self.node_types:
            start = node_offsets[node_type]
            # Next offset or end of array
            # We can find the end using the size of the original x_dict[node_type]
            end = start + x_dict[node_type].size(0)
            out_dict[node_type] = x_homo[start:end]
            
        return out_dict

def create_rgcn_model(metadata, hidden_channels=64, out_channels=64, num_layers=2):
    """Factory to create a Relational GCN."""
    return RGCN(metadata, hidden_channels, out_channels, num_layers)
