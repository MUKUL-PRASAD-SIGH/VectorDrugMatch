"""
src/models/kge.py - knowledge-graph embedding models (TransE, DistMult, ComplEx, RotatE) for the published-baseline comparison.

These are the standard KG-embedding baselines that the drug-repurposing literature (including the TxGNN paper) benchmarks against. They are
STRUCTURE-ONLY: unlike the VectorDrugMatch GCN they see no chemical fingerprints, so the comparison also measures how much chemistry contributes.

Scoring (higher = more plausible), as in the RotatE paper (Sun et al., ICLR 2019) and standard implementations:
  TransE    gamma - ||h + r - t||_1
  DistMult  <h, r, t>
  ComplEx   Re(<h, r, conj(t)>)
  RotatE    gamma - ||h o r - t||   with r a unit-modulus complex rotation
Training uses the self-adversarial negative sampling loss of the RotatE paper:
  L = -log sigma(s(h,r,t)) - sum_i softmax(alpha * s(h_i', r, t_i'))_i * log sigma(-s(h_i', r, t_i'))
Embedding dimension is the COMPLEX dimension for ComplEx/RotatE (2 * dim real parameters), matching usual practice.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

MODELS = ("TransE", "DistMult", "ComplEx", "RotatE")


class KGEModel(nn.Module):
    def __init__(self, name: str, n_entity: int, n_relation: int, dim: int = 128, gamma: float = 12.0):
        super().__init__()
        if name not in MODELS:
            raise ValueError(f"unknown model {name}")
        self.name, self.dim, self.gamma = name, dim, gamma
        ent_dim = dim * 2 if name in ("ComplEx", "RotatE") else dim
        rel_dim = dim * 2 if name == "ComplEx" else dim          # RotatE relation = phase only
        self.ent = nn.Embedding(n_entity, ent_dim)
        self.rel = nn.Embedding(n_relation, rel_dim)
        rng = (gamma + 2.0) / dim
        nn.init.uniform_(self.ent.weight, -rng, rng)
        nn.init.uniform_(self.rel.weight, -rng, rng)

    def score(self, h_idx, r_idx, t_idx):
        """h_idx (B,), r_idx (B,), t_idx (B,) or (B, N) -> (B,) or (B, N)."""
        h = self.ent(h_idx)
        r = self.rel(r_idx)
        t = self.ent(t_idx)
        if t.dim() == 3:                                          # (B, N, D) negatives
            h = h.unsqueeze(1)
            r = r.unsqueeze(1)
        if self.name == "TransE":
            return self.gamma - torch.norm(h + r - t, p=1, dim=-1)
        if self.name == "DistMult":
            return (h * r * t).sum(-1)
        if self.name == "ComplEx":
            hr, hi = torch.chunk(h, 2, dim=-1)
            rr, ri = torch.chunk(r, 2, dim=-1)
            tr, ti = torch.chunk(t, 2, dim=-1)
            return (hr * rr * tr + hi * rr * ti + hr * ri * ti - hi * ri * tr).sum(-1)
        hr, hi = torch.chunk(h, 2, dim=-1)                        # RotatE
        tr, ti = torch.chunk(t, 2, dim=-1)
        phase = r / ((self.gamma + 2.0) / self.dim / 3.141592653589793)
        rr, ri = torch.cos(phase), torch.sin(phase)
        re = hr * rr - hi * ri - tr
        im = hr * ri + hi * rr - ti
        return self.gamma - torch.stack([re, im], dim=0).norm(dim=0).sum(-1)

    def loss(self, h, r, t, nh, nt, alpha: float = 1.0):
        """Self-adversarial loss. nh/nt: (B, N) corrupted head/tail indices (head corruption where nt == t)."""
        pos = self.score(h, r, t)
        neg = self.score(nh.reshape(-1), r.repeat_interleave(nt.shape[1]), nt.reshape(-1)).view(nt.shape)
        with torch.no_grad():
            w = F.softmax(neg * alpha, dim=1)
        return (-F.logsigmoid(pos).mean() - (w * F.logsigmoid(-neg)).sum(1).mean()) / 2
