"""
src/models/baseline/mlp.py - Multi-Layer Perceptron Baseline
"""

from sklearn.neural_network import MLPClassifier
from src.models.baseline.base import BaseModel

class MLPModel(BaseModel):
    DEFAULTS = {
        "hidden_layer_sizes": (256, 128, 64),
        "activation": "relu",
        "solver": "adam",
        "alpha": 0.0001,
        "batch_size": 256,
        "learning_rate": "adaptive",
        "max_iter": 200,
        "random_state": 42,
        "early_stopping": True,
        "n_iter_no_change": 10
    }

    def __init__(self, **kwargs):
        params = self.DEFAULTS.copy()
        params.update(kwargs)
        self.model = MLPClassifier(**params)
        
    def train(self, X_train, y_train):
        self.model.fit(X_train, y_train)
        
    def predict_proba(self, X):
        return self.model.predict_proba(X)[:, 1]
