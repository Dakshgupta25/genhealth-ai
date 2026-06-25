"""
Model registry for GenHealth AI ML pipeline.

Handles:
- Saving trained model files to models_store/
- Loading models by name
- Listing available model versions
- Model metadata tracking
"""

import json
import logging
import os
import pickle
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "models_store")
REGISTRY_FILE = os.path.join(MODEL_STORE_DIR, "registry.json")

# Supported model names
REGISTERED_MODELS = ["diabetes", "hypertension", "thyroid", "heart"]


def ensure_model_store() -> None:
    """Create the model store directory if it doesn't exist."""
    os.makedirs(MODEL_STORE_DIR, exist_ok=True)


def save_model(
    model: Any,
    name: str,
    model_type: str = "xgb",
    metadata: Optional[Dict] = None,
) -> str:
    """
    Save a model artifact to the model store.

    Args:
        model:      The model object (XGBClassifier, state_dict, or StandardScaler).
        name:       Model name (e.g., 'diabetes').
        model_type: 'xgb' | 'nn' | 'scaler'
        metadata:   Optional dict of training metadata (metrics, dataset size, etc.)

    Returns:
        Absolute path to the saved file.
    """
    ensure_model_store()

    ext = {"xgb": ".pkl", "nn": ".pth", "scaler": ".pkl"}.get(model_type, ".pkl")
    filename = f"{name}_{model_type}{ext}"
    filepath = os.path.join(MODEL_STORE_DIR, filename)

    try:
        if model_type == "nn":
            import torch
            torch.save(model, filepath)
        else:
            with open(filepath, "wb") as f:
                pickle.dump(model, f)

        logger.info("Saved model '%s' → %s", name, filepath)

        # Update registry
        _update_registry(name, model_type, filepath, metadata)
        return filepath

    except Exception as exc:
        logger.error("Failed to save model '%s': %s", name, exc)
        raise


def load_model(name: str, model_type: str = "xgb") -> Optional[Any]:
    """
    Load a model artifact from the model store.

    Args:
        name:       Model name (e.g., 'diabetes').
        model_type: 'xgb' | 'nn' | 'scaler'

    Returns:
        Loaded model object or None if not found.
    """
    ext = {"xgb": ".pkl", "nn": ".pth", "scaler": ".pkl"}.get(model_type, ".pkl")
    filename = f"{name}_{model_type}{ext}"
    filepath = os.path.join(MODEL_STORE_DIR, filename)

    if not os.path.exists(filepath):
        logger.warning("Model file not found: %s", filepath)
        return None

    try:
        if model_type == "nn":
            import torch
            return torch.load(filepath, map_location="cpu")
        else:
            with open(filepath, "rb") as f:
                return pickle.load(f)
    except Exception as exc:
        logger.error("Failed to load model '%s': %s", filepath, exc)
        return None


def list_models() -> List[Dict]:
    """
    List all registered model artifacts and their metadata.

    Returns:
        List of model registry entry dicts.
    """
    registry = _load_registry()
    return registry.get("models", [])


def get_model_status() -> Dict[str, Dict]:
    """
    Return the availability status of all disease models.

    Returns:
        Dict mapping model name → {xgb_exists, nn_exists, scaler_exists, last_trained}
    """
    status = {}
    for disease in REGISTERED_MODELS:
        xgb_path = os.path.join(MODEL_STORE_DIR, f"{disease}_xgb.pkl")
        nn_path = os.path.join(MODEL_STORE_DIR, f"{disease}_nn.pth")
        scaler_path = os.path.join(MODEL_STORE_DIR, f"{disease}_scaler.pkl")
        status[disease] = {
            "xgb_exists": os.path.exists(xgb_path),
            "nn_exists": os.path.exists(nn_path),
            "scaler_exists": os.path.exists(scaler_path),
            "fully_trained": (
                os.path.exists(xgb_path) and
                os.path.exists(nn_path) and
                os.path.exists(scaler_path)
            ),
        }
    return status


def delete_model(name: str, model_type: str = "xgb") -> bool:
    """Delete a model file from the store."""
    ext = {"xgb": ".pkl", "nn": ".pth", "scaler": ".pkl"}.get(model_type, ".pkl")
    filepath = os.path.join(MODEL_STORE_DIR, f"{name}_{model_type}{ext}")
    if os.path.exists(filepath):
        os.remove(filepath)
        logger.info("Deleted model: %s", filepath)
        return True
    return False


# ─── Registry helpers ─────────────────────────────────────────────────────────

def _load_registry() -> Dict:
    """Load the JSON registry file."""
    if not os.path.exists(REGISTRY_FILE):
        return {"models": []}
    try:
        with open(REGISTRY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"models": []}


def _update_registry(
    name: str, model_type: str, filepath: str, metadata: Optional[Dict]
) -> None:
    """Update the registry with a new model entry."""
    registry = _load_registry()
    entry = {
        "name": name,
        "type": model_type,
        "path": filepath,
        "saved_at": datetime.utcnow().isoformat(),
        "metadata": metadata or {},
    }
    # Remove old entry for same name+type
    registry["models"] = [
        m for m in registry["models"]
        if not (m["name"] == name and m["type"] == model_type)
    ]
    registry["models"].append(entry)

    try:
        with open(REGISTRY_FILE, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception as exc:
        logger.warning("Could not update registry: %s", exc)
