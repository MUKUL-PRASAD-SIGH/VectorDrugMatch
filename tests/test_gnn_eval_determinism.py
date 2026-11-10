"""Regression test: GNN predictions must be deterministic in eval mode (dropout must follow model.eval()).
Found 2026-11-10: GCN/GraphSAGE/GAT used F.dropout(training=self.training) inside to_hetero, which froze training=True at FX-trace time.
Synthetic tiny graph; diagnostic only."""
import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")


def _graph():
    from torch_geometric.data import HeteroData
    torch.manual_seed(0)
    d = HeteroData()
    d["drug"].x, d["disease"].x, d["gene"].x = torch.rand(30, 16), torch.rand(20, 3), torch.ones(15, 1)
    e = lambda a, b, k: torch.stack([torch.randint(0, a, (k,)), torch.randint(0, b, (k,))])
    d["drug", "binds", "gene"].edge_index = e(30, 15, 60)
    d["gene", "rev_binds", "drug"].edge_index = d["drug", "binds", "gene"].edge_index.flip(0)
    d["disease", "associates", "gene"].edge_index = e(20, 15, 50)
    d["gene", "rev_associates", "disease"].edge_index = d["disease", "associates", "gene"].edge_index.flip(0)
    d["gene", "interacts", "gene"].edge_index = e(15, 15, 40)
    return d, torch.stack([torch.randint(0, 30, (20,)), torch.randint(0, 20, (20,))])


@pytest.mark.parametrize("name", ["GCN", "GraphSAGE", "GAT", "RGCN", "HGT"])
def test_eval_mode_is_deterministic(name):
    warnings.filterwarnings("ignore")
    from src.models.gnn.base import GNNLinkPredictionModel
    from src.models.gnn.gat import create_gat_model
    from src.models.gnn.gcn import create_gcn_model
    from src.models.gnn.graphsage import create_graphsage_model
    from src.models.gnn.hgt import create_hgt_model
    from src.models.gnn.rgcn import create_rgcn_model
    d, q = _graph()
    make = {"GCN": create_gcn_model, "GraphSAGE": create_graphsage_model, "GAT": lambda m, **k: create_gat_model(m, heads=2, **k),
            "RGCN": create_rgcn_model, "HGT": lambda m, **k: create_hgt_model(m, heads=2, **k)}[name]
    m = GNNLinkPredictionModel(make(d.metadata(), hidden_channels=16, out_channels=16), in_channels=16, hidden_channels=8)
    with torch.no_grad():
        m(d.x_dict, d.edge_index_dict, q)
    m.eval()
    with torch.no_grad():
        a, b = m(d.x_dict, d.edge_index_dict, q), m(d.x_dict, d.edge_index_dict, q)
    assert torch.allclose(a, b), f"{name}: eval-mode predictions differ between two identical forward passes (dropout active in eval?)"
