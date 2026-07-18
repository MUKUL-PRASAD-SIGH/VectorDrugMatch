"""
src/models/baseline/random_forest.py - Random Forest Baseline
"""

from sklearn.ensemble import RandomForestClassifier
from src.models.baseline.base import BaseModel

class RandomForestModel(BaseModel):
    DEFAULTS = {
        "n_estimators": 100,
        "max_depth": 10,
        "class_weight": "balanced",
        "random_state": 42,
        "n_jobs": -1
    }

    def __init__(self, **kwargs):
        params = self.DEFAULTS.copy()
        params.update(kwargs)
        self.model = RandomForestClassifier(**params)
        
    def train(self, X_train, y_train):
        self.model.fit(X_train, y_train)
        
    def predict_proba(self, X):
        return self.model.predict_proba(X)[:, 1]
