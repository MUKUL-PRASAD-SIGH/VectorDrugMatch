"""
src/models/baseline/naive_bayes.py - Gaussian Naive Bayes Baseline
"""

from sklearn.naive_bayes import GaussianNB
from src.models.baseline.base import BaseModel

class NaiveBayesModel(BaseModel):
    DEFAULTS = {}

    def __init__(self, **kwargs):
        params = self.DEFAULTS.copy()
        params.update(kwargs)
        self.model = GaussianNB(**params)
        
    def train(self, X_train, y_train):
        self.model.fit(X_train, y_train)
        
    def predict_proba(self, X):
        return self.model.predict_proba(X)[:, 1]
