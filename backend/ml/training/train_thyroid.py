"""
Training script for Thyroid risk model.
Generates synthetic clinical data, optimizes XGBoost using Optuna,
trains a PyTorch feedforward network, and registers the ensemble model.
"""

import logging
import os
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, f1_score, classification_report

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

import optuna
import xgboost as xgb

from ml.risk_models.model_registry import save_model
from ml.risk_models.thyroid_model import ThyroidNet, THYROID_FEATURES

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("train_thyroid")

def generate_synthetic_thyroid_data(n_samples: int = 1500, random_state: int = 42) -> pd.DataFrame:
    """Generate statistically realistic synthetic dataset for thyroid training."""
    np.random.seed(random_state)
    
    # Demographics
    age = np.random.randint(18, 85, size=n_samples)
    gender_male = np.random.binomial(1, 0.35, size=n_samples)  # Enforce higher proportion of females
    
    # Lab metrics
    # TSH has a skewed distribution (log-normal is a good fit)
    latest_tsh = np.random.lognormal(mean=0.9, sigma=0.8, size=n_samples)
    latest_tsh = np.clip(latest_tsh, 0.05, 35.0)
    
    # Personal history & recurrence (based on TSH indicators)
    has_thyroid_history = np.zeros(n_samples)
    prob_history = 1 / (1 + np.exp(-(latest_tsh - 5.5) * 0.8))
    # Females are more likely to have history
    prob_history = prob_history * (1.5 - 0.5 * gender_male)
    has_thyroid_history = np.random.rand(n_samples) < prob_history
    has_thyroid_history = has_thyroid_history.astype(int)
    
    thyroid_med_count = np.zeros(n_samples)
    thyroid_med_count[has_thyroid_history == 1] = np.random.poisson(1.1, size=np.sum(has_thyroid_history))
    
    # Comorbidity (Autoimmune diabetes-thyroid association)
    has_diabetes_history = np.random.binomial(1, 0.15, size=n_samples)
    
    # Family history
    parent_thyroid = np.random.binomial(1, 0.18, size=n_samples)
    family_thyroid_count = parent_thyroid + np.random.binomial(1, 0.10, size=n_samples)
    
    # Lifestyle & general features
    exercise_regularity = np.random.uniform(0, 1, size=n_samples)
    disease_count = np.random.poisson(0.6, size=n_samples) + has_thyroid_history + has_diabetes_history
    
    # Create DataFrame
    df = pd.DataFrame({
        "age": age,
        "gender_male": gender_male,
        "latest_tsh": latest_tsh,
        "has_thyroid_history": has_thyroid_history,
        "thyroid_med_count": thyroid_med_count,
        "parent_thyroid": parent_thyroid,
        "family_thyroid_count": family_thyroid_count,
        "has_diabetes_history": has_diabetes_history,
        "disease_count": disease_count,
        "exercise_regularity": exercise_regularity
    })
    
    score = (
        0.02 * (age - 35)
        - 1.2 * gender_male
        + 0.5 * (latest_tsh - 4.0)
        + 2.0 * has_thyroid_history
        + 1.0 * parent_thyroid
        + 0.8 * has_diabetes_history
        - 0.5 * exercise_regularity
    )
    
    threshold = np.percentile(score, 70)  # ~30% positive cases
    df["target"] = (score >= threshold).astype(int)
    
    # Flip a tiny random fraction (e.g. 1%) to add realistic noise
    flip_mask = np.random.rand(n_samples) < 0.01
    df.loc[flip_mask, "target"] = 1 - df.loc[flip_mask, "target"]
    df["target"] = df["target"].astype(int)

    
    return df

def main():
    logger.info("Generating synthetic thyroid dataset...")
    df = generate_synthetic_thyroid_data(1800, random_state=42)
    
    X = df[THYROID_FEATURES].values
    y = df["target"].values
    
    # Split
    X_train_val, X_test, y_train_val, y_test = train_test_split(X, y, test_size=0.10, random_state=42, stratify=y)
    X_train, X_val, y_train, y_val = train_test_split(X_train_val, y_train_val, test_size=0.1111, random_state=42, stratify=y_train_val)
    
    logger.info(f"Splits: Train={X_train.shape[0]}, Val={X_val.shape[0]}, Test={X_test.shape[0]}")
    
    # Fit and save Scaler
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # Train XGBoost with Optuna
    logger.info("Starting XGBoost hyperparameter optimization with Optuna...")
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 40, 150),
            "max_depth": trial.suggest_int("max_depth", 3, 6),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 0.9),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 0.9),
            "use_label_encoder": False,
            "eval_metric": "logloss"
        }
        model = xgb.XGBClassifier(**params)
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        preds = model.predict_proba(X_val)[:, 1]
        return roc_auc_score(y_val, preds)
        
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=50)
    best_params = study.best_params
    best_params["use_label_encoder"] = False
    best_params["eval_metric"] = "logloss"
    logger.info(f"Best XGBoost Params: {best_params}")
    
    # Train final XGBoost model
    xgb_model = xgb.XGBClassifier(**best_params)
    xgb_model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    
    # Train PyTorch Neural Network
    logger.info("Training PyTorch Neural Network model...")
    train_dataset = TensorDataset(torch.FloatTensor(X_train_scaled), torch.FloatTensor(y_train).unsqueeze(1))
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    
    nn_model = ThyroidNet(input_size=len(THYROID_FEATURES))
    criterion = nn.BCELoss()
    optimizer = optim.Adam(nn_model.parameters(), lr=0.005, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=15, gamma=0.5)
    
    epochs = 50
    for epoch in range(epochs):
        nn_model.train()
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = nn_model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
        scheduler.step()
        
    # Evaluate PyTorch on validation set
    nn_model.eval()
    with torch.no_grad():
        val_nn_preds = nn_model(torch.FloatTensor(X_val_scaled)).numpy().squeeze()
    val_nn_auc = roc_auc_score(y_val, val_nn_preds)
    logger.info(f"Validation PyTorch AUC-ROC: {val_nn_auc:.4f}")
    
    # Evaluate Ensemble on Test Set
    logger.info("Evaluating Ensemble on Test Set...")
    xgb_test_preds = xgb_model.predict_proba(X_test)[:, 1]
    
    nn_model.eval()
    with torch.no_grad():
        nn_test_preds = nn_model(torch.FloatTensor(X_test_scaled)).numpy().squeeze()
        
    # Ensemble (0.60 XGB + 0.40 PyTorch)
    ensemble_test_preds = 0.60 * xgb_test_preds + 0.40 * nn_test_preds
    ensemble_test_labels = (ensemble_test_preds >= 0.50).astype(int)
    
    auc_roc = roc_auc_score(y_test, ensemble_test_preds)
    f1 = f1_score(y_test, ensemble_test_labels)
    
    logger.info("=================== TEST SET EVALUATION ===================")
    logger.info(f"Ensemble AUC-ROC : {auc_roc:.4f} (Target: > 0.82)")
    logger.info(f"Ensemble F1-Score: {f1:.4f} (Target: > 0.75)")
    logger.info("\n" + classification_report(y_test, ensemble_test_labels))
    
    if auc_roc < 0.82 or f1 < 0.75:
        logger.error("Model did not meet target performance metrics!")
        raise ValueError(f"Target metrics not met. AUC: {auc_roc:.4f}, F1: {f1:.4f}")
        
    # Save models
    logger.info("Saving trained models to registry...")
    save_model(xgb_model, name="thyroid", model_type="xgb", metadata={"auc_roc": auc_roc, "f1_score": f1})
    save_model(nn_model.state_dict(), name="thyroid", model_type="nn", metadata={"auc_roc": auc_roc, "f1_score": f1})
    save_model(scaler, name="thyroid", model_type="scaler", metadata={"features": THYROID_FEATURES})
    logger.info("All model artifacts saved successfully.")

if __name__ == "__main__":
    main()
