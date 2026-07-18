"""
src/models/baseline/logistic.py - Logistic Regression Baseline
"""

from sklearn.linear_model import LogisticRegression
from src.models.baseline.base import BaseModel

class LogisticRegressionModel(BaseModel):
    DEFAULTS = {
        "max_iter": 1000,
        "class_weight": "balanced",
        "random_state": 42
    }

    def __init__(self, **kwargs):
        params = self.DEFAULTS.copy()
        params.update(kwargs)
        self.model = LogisticRegression(**params)
        
    def train(self, X_train, y_train):
        self.model.fit(X_train, y_train)
        
    def predict_proba(self, X):
        # Return probability for the positive class (index 1)
        return self.model.predict_proba(X)[:, 1]
