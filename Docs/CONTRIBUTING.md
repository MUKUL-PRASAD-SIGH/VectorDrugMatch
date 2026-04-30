# 🤝 CONTRIBUTING.md

Thank you for contributing to VectorDrugMatch! This guide covers the workflow for the 4-person core team and any external contributors.

---

## Development Workflow

### Branch Strategy

```
main            ← stable, always deployable
├── dev         ← integration branch, merge PRs here first
│   ├── feat/data-pipeline      ← Nikita
│   ├── feat/gcn-model          ← Arpit
│   ├── feat/ndpi-scoring       ← Mukul
│   └── feat/streamlit-ui       ← Swastik
```

**Rules:**
- Never commit directly to `main`
- Create a branch per feature/week: `feat/week3-gat-model`
- Open a PR to `dev`; another team member reviews before merging
- Merge `dev` → `main` at the end of each week

### Daily Git Workflow

```bash
# Start of day — pull latest
git checkout dev
git pull origin dev
git checkout feat/your-feature

# End of day — push your work
git add .
git commit -m "feat: implement tanimoto similarity scoring"
git push origin feat/your-feature
```

### Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add PubMed literature scoring
fix: handle missing SMILES in RDKit computation
docs: update DATASETS.md with ChEMBL query
test: add unit tests for equity scoring
refactor: clean up graph_builder.py
```

---

## Code Standards

### Python Style
- Format with **Black**: `black src/ tests/`
- Lint with **flake8**: `flake8 src/ tests/`
- Type hints required on all public functions
- Docstrings required on all public functions and classes

```python
def tanimoto_similarity(smiles1: str, smiles2: str) -> float:
    """
    Compute Tanimoto similarity between two molecules.

    Args:
        smiles1: SMILES string for molecule 1
        smiles2: SMILES string for molecule 2

    Returns:
        Tanimoto coefficient [0.0, 1.0]. Returns 0.0 if either SMILES is invalid.
    """
    ...
```

### Testing
- Write tests in `tests/` for every module you create
- Run tests before opening a PR: `pytest tests/ -v`
- Target: 80% coverage on `src/`

---

## Pull Request Template

When opening a PR, include:

```markdown
## What this PR does
Brief description of changes.

## How to test
Step-by-step instructions.

## Checklist
- [ ] Tests pass (`pytest tests/`)
- [ ] Code formatted (`black src/`)
- [ ] Docstrings added
- [ ] MASTER_PLAN.md tasks checked off
```

---

## Weekly Standup Format (15 mins)

Every Monday at 10 AM:
1. What did you complete last week?
2. What are you working on this week?
3. Any blockers?

Update your task checkboxes in `MASTER_PLAN.md` before the standup.
