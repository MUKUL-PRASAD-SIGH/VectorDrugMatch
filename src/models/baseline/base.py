"""
src/models/baseline/base.py - Baseline Model Interface

Defines the abstract base class that all classical ML models must implement.
Ensures a clean, unified API for training and evaluation.
"""

from abc import ABC, abstractmethod
import joblib

class BaseModel(ABC):
    """Abstract base class for all tabular ML models."""
    
    @abstractmethod
    def train(self, X_train, y_train):
        """Train the model on the provided dataset."""
        pass
        
    @abstractmethod
    def predict_proba(self, X):
        """Predict probabilities for the positive class (link exists)."""
        pass
        
    def predict(self, X):
        """Predict binary class labels (0 or 1)."""
        if hasattr(self, "model") and hasattr(self.model, "predict"):
            return self.model.predict(X)
        raise NotImplementedError("predict() not implemented for this model.")
        
    def get_params(self):
        """Get model parameters for logging."""
        if hasattr(self, "model") and hasattr(self.model, "get_params"):
            return self.model.get_params()
        return {}
        
    def save(self, filepath: str):
        """Save the trained model to disk."""
        if hasattr(self, "model"):
            joblib.dump(self.model, filepath)
        else:
            raise NotImplementedError("Model instance not found for saving.")
            
    def load(self, filepath: str):
        """Load a trained model from disk."""
        self.model = joblib.load(filepath)
