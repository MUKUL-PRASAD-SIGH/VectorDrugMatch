"""
src/models/baseline/xgboost_model.py - XGBoost Baseline
"""

try:
    from xgboost import XGBClassifier
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

from src.models.baseline.base import BaseModel

class XGBoostModel(BaseModel):
    DEFAULTS = {
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "scale_pos_weight": 5.0,  # Handle class imbalance
        "random_state": 42,
        "n_jobs": -1,
        "eval_metric": "logloss"
    }

    def __init__(self, **kwargs):
        if not XGB_AVAILABLE:
            raise ImportError("XGBoost is not installed. Run: pip install xgboost")
            
        params = self.DEFAULTS.copy()
        params.update(kwargs)
        self.model = XGBClassifier(**params)
        
    def train(self, X_train, y_train):
        self.model.fit(X_train, y_train)
        
    def predict_proba(self, X):
        return self.model.predict_proba(X)[:, 1]
