"""
Training script for Diabetes risk model.
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
from ml.risk_models.diabetes_model import DiabetesNet, DIABETES_FEATURES

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("train_diabetes")

def generate_synthetic_diabetes_data(n_samples: int = 1500, random_state: int = 42) -> pd.DataFrame:
    """Generate statistically realistic synthetic dataset for diabetes training."""
    np.random.seed(random_state)
    
    # Demographics
    age = np.random.randint(18, 85, size=n_samples)
    gender_male = np.random.binomial(1, 0.48, size=n_samples)
    
    # Clinical/Anthropometric
    bmi = np.random.normal(27.0, 6.0, size=n_samples)
    bmi = np.clip(bmi, 15.0, 48.0)
    latest_bmi = bmi + np.random.normal(0, 0.5, size=n_samples)
    
    # Lab metrics
    latest_blood_sugar_fasting = np.random.normal(105, 30, size=n_samples)
    latest_blood_sugar_fasting = np.clip(latest_blood_sugar_fasting, 65, 280)
    
    # HbA1c is strongly correlated with fasting blood sugar
    latest_hba1c = 4.0 + (latest_blood_sugar_fasting - 70) * 0.03 + np.random.normal(0, 0.4, size=n_samples)
    latest_hba1c = np.clip(latest_hba1c, 4.0, 13.0)
    
    # Personal history & recurrence (based on lab indicators)
    has_diabetes_history = np.zeros(n_samples)
    # Higher baseline probability of history if HbA1c > 6.5 or fasting sugar > 126
    prob_history = 1 / (1 + np.exp(-(latest_hba1c - 6.2) * 2.0))
    has_diabetes_history = np.random.rand(n_samples) < prob_history
    has_diabetes_history = has_diabetes_history.astype(int)
    
    diabetes_recurrence_count = np.zeros(n_samples)
    diabetes_recurrence_count[has_diabetes_history == 1] = np.random.poisson(1.5, size=np.sum(has_diabetes_history))
    
    # Family history
    parent_diabetes = np.random.binomial(1, 0.20, size=n_samples)
    grandparent_diabetes = np.random.binomial(1, 0.15, size=n_samples)
    sibling_diabetes = np.random.binomial(1, 0.12, size=n_samples)
    family_diabetes_count = parent_diabetes + grandparent_diabetes + sibling_diabetes
    
    # Associated/comorbid conditions
    thyroid_med_count = np.random.binomial(1, 0.08, size=n_samples) * np.random.randint(1, 3, size=n_samples)
    disease_count = np.random.poisson(0.8, size=n_samples) + has_diabetes_history
    
    # Lifestyle factors
    exercise_regularity = np.random.uniform(0, 1, size=n_samples)
    diet_quality_score = np.random.uniform(0, 1, size=n_samples)
    
    # Create DataFrame
    df = pd.DataFrame({
        "age": age,
        "gender_male": gender_male,
        "bmi": bmi,
        "latest_bmi": latest_bmi,
        "latest_blood_sugar_fasting": latest_blood_sugar_fasting,
        "latest_hba1c": latest_hba1c,
        "has_diabetes_history": has_diabetes_history,
        "diabetes_recurrence_count": diabetes_recurrence_count,
        "disease_count": disease_count,
        "parent_diabetes": parent_diabetes,
        "grandparent_diabetes": grandparent_diabetes,
        "sibling_diabetes": sibling_diabetes,
        "family_diabetes_count": family_diabetes_count,
        "thyroid_med_count": thyroid_med_count,
        "exercise_regularity": exercise_regularity,
        "diet_quality_score": diet_quality_score
    })
    
    # Generate label (y) based on realistic weights to simulate clinical indicators
    # and hereditary risks
    logit = (
        -4.2
        + 0.025 * (age - 40)
        + 0.08 * (bmi - 25)
        + 0.02 * (latest_blood_sugar_fasting - 100)
        + 1.1 * (latest_hba1c - 5.7)
        + 1.5 * has_diabetes_history
        + 0.8 * parent_diabetes
        + 0.4 * grandparent_diabetes
        + 0.6 * sibling_diabetes
        - 0.8 * exercise_regularity
        - 0.6 * diet_quality_score
    )
    
    prob = 1 / (1 + np.exp(-logit))
    # Add random noise draw for target classification
    df["target"] = (np.random.rand(n_samples) < prob).astype(int)
    
    return df

def main():
    logger.info("Generating synthetic diabetes dataset...")
    df = generate_synthetic_diabetes_data(1800, random_state=42)
    
    X = df[DIABETES_FEATURES].values
    y = df["target"].values
    
    # Split: 80% train, 10% val, 10% test
    X_train_val, X_test, y_train_val, y_test = train_test_split(X, y, test_size=0.10, random_state=42, stratify=y)
    X_train, X_val, y_train, y_val = train_test_split(X_train_val, y_train_val, test_size=0.1111, random_state=42, stratify=y_train_val)
    
    logger.info(f"Splits: Train={X_train.shape[0]}, Val={X_val.shape[0]}, Test={X_test.shape[0]}")
    
    # ─── Part 1: Fit and save Scaler ───
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # ─── Part 2: Train XGBoost with Optuna ───
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
    
    # ─── Part 3: Train PyTorch Neural Network ───
    logger.info("Training PyTorch Neural Network model...")
    train_dataset = TensorDataset(torch.FloatTensor(X_train_scaled), torch.FloatTensor(y_train).unsqueeze(1))
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    
    nn_model = DiabetesNet(input_size=len(DIABETES_FEATURES))
    criterion = nn.BCELoss()
    optimizer = optim.Adam(nn_model.parameters(), lr=0.005, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=15, gamma=0.5)
    
    epochs = 50
    for epoch in range(epochs):
        nn_model.train()
        epoch_loss = 0.0
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = nn_model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * batch_x.size(0)
        scheduler.step()
        
    # Evaluate PyTorch on validation set
    nn_model.eval()
    with torch.no_grad():
        val_nn_preds = nn_model(torch.FloatTensor(X_val_scaled)).numpy().squeeze()
        
    val_nn_auc = roc_auc_score(y_val, val_nn_preds)
    logger.info(f"Validation PyTorch AUC-ROC: {val_nn_auc:.4f}")
    
    # ─── Part 4: Evaluate Ensemble on Test Set ───
    logger.info("Evaluating Ensemble on Test Set...")
    xgb_test_preds = xgb_model.predict_proba(X_test)[:, 1]
    
    nn_model.eval()
    with torch.no_grad():
        nn_test_preds = nn_model(torch.FloatTensor(X_test_scaled)).numpy().squeeze()
        
    # Weighted average ensemble (0.60 XGB + 0.40 PyTorch)
    ensemble_test_preds = 0.60 * xgb_test_preds + 0.40 * nn_test_preds
    ensemble_test_labels = (ensemble_test_preds >= 0.50).astype(int)
    
    auc_roc = roc_auc_score(y_test, ensemble_test_preds)
    f1 = f1_score(y_test, ensemble_test_labels)
    
    logger.info("=================== TEST SET EVALUATION ===================")
    logger.info(f"Ensemble AUC-ROC : {auc_roc:.4f} (Target: > 0.82)")
    logger.info(f"Ensemble F1-Score: {f1:.4f} (Target: > 0.75)")
    logger.info("\n" + classification_report(y_test, ensemble_test_labels))
    
    # Verify success criteria
    if auc_roc < 0.82 or f1 < 0.75:
        logger.error("Model did not meet target performance metrics!")
        raise ValueError(f"Target metrics not met. AUC: {auc_roc:.4f}, F1: {f1:.4f}")
        
    # ─── Part 5: Save models ───
    logger.info("Saving trained models to registry...")
    save_model(xgb_model, name="diabetes", model_type="xgb", metadata={"auc_roc": auc_roc, "f1_score": f1})
    save_model(nn_model.state_dict(), name="diabetes", model_type="nn", metadata={"auc_roc": auc_roc, "f1_score": f1})
    save_model(scaler, name="diabetes", model_type="scaler", metadata={"features": DIABETES_FEATURES})
    logger.info("All model artifacts saved successfully.")

if __name__ == "__main__":
    main()
