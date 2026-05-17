"""
Fraud Detection Model Training Pipeline
Trains XGBoost model on FSI_DEMO.ANALYTICS_BANKING.V_FRAUD_TRAINING_SET
"""

import os
import pickle
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score, 
    precision_recall_curve, roc_curve
)
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
import seaborn as sns
from snowflake.snowpark import Session

# Model version
MODEL_VERSION = "v1.0.0"
MODEL_DATE = datetime.now().strftime("%Y%m%d_%H%M%S")

print("=" * 80)
print("FSI FRAUD DETECTION MODEL TRAINING")
print("=" * 80)
print(f"Model Version: {MODEL_VERSION}")
print(f"Training Date: {MODEL_DATE}")
print()

# Connect to Snowflake
print("Connecting to Snowflake...")
session = Session.builder.configs({
    "connection_name": "workbench",
    "database": "FSI_DEMO",
    "schema": "ANALYTICS_BANKING"
}).create()
print("✓ Connected to Snowflake\n")

# Load training data
print("Loading training data from V_FRAUD_TRAINING_SET...")
df = session.sql("SELECT * FROM V_FRAUD_TRAINING_SET").to_pandas()
print(f"✓ Loaded {len(df):,} transactions")
# Convert boolean columns to int (Snowflake booleans come as objects)

# DEBUG: Check if CUST_PRIOR_FRAUD exists
print("\nColumn check:")
print(f"  CUST_PRIOR_FRAUD exists: {'CUST_PRIOR_FRAUD' in df.columns}")
if 'CUST_PRIOR_FRAUD' in df.columns:
    print(f"  CUST_PRIOR_FRAUD dtype: {df['CUST_PRIOR_FRAUD'].dtype}")
    print(f"  CUST_PRIOR_FRAUD sample values: {df['CUST_PRIOR_FRAUD'].head().tolist()}")
print()

# Convert boolean columns to int (Snowflake booleans come as objects)

# Handle None values first
bool_cols = ['IS_FRAUD', 'IS_INTERNATIONAL', 'IS_HIGH_VALUE', 'IS_LATE_NIGHT', 
             'IS_WEEKEND']
for col in bool_cols:
    if col in df.columns:
        df[col] = df[col].fillna(0).astype(int)

print(f"  Fraud rate: {df['IS_FRAUD'].mean():.2%}")
print(f"  Fraud cases: {df['IS_FRAUD'].sum():,}")
print(f"  Legitimate cases: {(~df['IS_FRAUD']).sum():,}\n")

# Feature columns
feature_cols = [
    'TRANSACTION_AMOUNT', 'IS_INTERNATIONAL', 'IS_HIGH_VALUE',
    'TXN_HOUR', 'IS_LATE_NIGHT', 'IS_WEEKEND',
    'CHANNEL_ENCODED', 'TXN_TYPE_ENCODED',
    'TXNS_LAST_24H', 'TXNS_LAST_1H', 'AMOUNT_LAST_24H',
    'CUST_AVG_AMOUNT', 'CUST_STDDEV_AMOUNT', 'AMOUNT_ZSCORE',
    'CREDIT_SCORE', 'CUSTOMER_TENURE_YEARS',
    'RISK_RATING_ENCODED'
]

# Prepare features and target
X = df[feature_cols].fillna(0)
y = df['IS_FRAUD'].astype(int)
transaction_keys = df['TRANSACTION_KEY']

print("Feature engineering complete")
print(f"  Features: {len(feature_cols)}")
print(f"  Missing values handled: fillna(0)\n")

# Train/test split (stratified)
print("Splitting data (80/20, stratified)...")
X_train, X_test, y_train, y_test, keys_train, keys_test = train_test_split(
    X, y, transaction_keys, 
    test_size=0.2, 
    random_state=42, 
    stratify=y
)
print(f"✓ Training set: {len(X_train):,} samples ({y_train.mean():.2%} fraud)")
print(f"✓ Test set: {len(X_test):,} samples ({y_test.mean():.2%} fraud)\n")

# Calculate scale_pos_weight for class imbalance
scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
print(f"Class imbalance handling:")
print(f"  scale_pos_weight: {scale_pos_weight:.2f}\n")

# Train XGBoost model
print("Training XGBoost model...")
model = xgb.XGBClassifier(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    scale_pos_weight=scale_pos_weight,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    eval_metric='auc',
    early_stopping_rounds=10
)

model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=False
)
print("✓ Model training complete\n")

# Predictions
print("Generating predictions...")
y_pred_proba = model.predict_proba(X_test)[:, 1]
y_pred = (y_pred_proba > 0.5).astype(int)
print("✓ Predictions generated\n")

# Evaluation metrics
print("=" * 80)
print("MODEL EVALUATION")
print("=" * 80)

# Classification report
print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=['Legitimate', 'Fraud']))

# Confusion matrix
cm = confusion_matrix(y_test, y_pred)
print("\nConfusion Matrix:")
print(f"                 Predicted")
print(f"                 Legit  Fraud")
print(f"Actual Legit     {cm[0,0]:5d}  {cm[0,1]:5d}")
print(f"       Fraud     {cm[1,0]:5d}  {cm[1,1]:5d}")

# AUC-ROC
auc_score = roc_auc_score(y_test, y_pred_proba)
print(f"\nAUC-ROC Score: {auc_score:.4f}")

# Feature importance
print("\n" + "=" * 80)
print("FEATURE IMPORTANCE (Top 10)")
print("=" * 80)
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

for idx, row in feature_importance.head(10).iterrows():
    print(f"{row['feature']:30s} {row['importance']:.4f}")

# SHAP analysis
print("\n" + "=" * 80)
print("SHAP ANALYSIS")
print("=" * 80)
print("Computing SHAP values (this may take a moment)...")

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

print("✓ SHAP values computed")
print(f"  Mean absolute SHAP value: {np.abs(shap_values).mean():.4f}\n")

# Save model
model_dir = os.path.expanduser("~/snowflake_demos/fsi_demo/models/artifacts")
os.makedirs(model_dir, exist_ok=True)

model_path = f"{model_dir}/fraud_model_{MODEL_DATE}.pkl"
with open(model_path, 'wb') as f:
    pickle.dump({
        'model': model,
        'feature_cols': feature_cols,
        'version': MODEL_VERSION,
        'trained_at': MODEL_DATE,
        'metrics': {
            'auc_roc': auc_score,
            'test_size': len(X_test),
            'fraud_rate': y_test.mean()
        }
    }, f)

print(f"✓ Model saved to: {model_path}\n")

# Score all transactions and write to Snowflake
print("=" * 80)
print("SCORING ALL TRANSACTIONS")
print("=" * 80)

# Score training data
print("Scoring all training data...")
all_proba = model.predict_proba(X)[:, 1]
all_pred = (all_proba > 0.5).astype(int)

# Create results DataFrame
results_df = pd.DataFrame({
    'TRANSACTION_KEY': transaction_keys,
    'FRAUD_PROBABILITY': all_proba,
    'FRAUD_PREDICTION': all_pred,
    'MODEL_VERSION': MODEL_VERSION,
    'SCORED_AT': datetime.now()
})

print(f"✓ Scored {len(results_df):,} transactions")
print(f"  Predicted fraud: {all_pred.sum():,} ({all_pred.mean():.2%})\n")

# Write to Snowflake
print("Writing predictions to FSI_DEMO.ANALYTICS_BANKING.ML_FRAUD_SCORES...")

# Create table if not exists
session.sql("""
CREATE TABLE IF NOT EXISTS FSI_DEMO.ANALYTICS_BANKING.ML_FRAUD_SCORES (
    TRANSACTION_KEY NUMBER,
    FRAUD_PROBABILITY FLOAT,
    FRAUD_PREDICTION BOOLEAN,
    MODEL_VERSION VARCHAR(50),
    SCORED_AT TIMESTAMP_NTZ
)
""").collect()

# Convert to Snowpark DataFrame and write
from snowflake.snowpark.functions import col
results_sp = session.create_dataframe(results_df)
results_sp.write.mode("overwrite").save_as_table("ML_FRAUD_SCORES")

print("✓ Predictions written to Snowflake\n")

# Score new transactions from TRANSACTION_STAGING
print("=" * 80)
print("SCORING NEW TRANSACTIONS FROM STAGING")
print("=" * 80)

staging_query = """
SELECT 
    t.TRANSACTION_ID AS TRANSACTION_KEY,
    t.TRANSACTION_AMOUNT,
    CAST(t.IS_INTERNATIONAL AS INT) AS IS_INTERNATIONAL,
    CASE WHEN t.TRANSACTION_AMOUNT > 5000 THEN 1 ELSE 0 END AS IS_HIGH_VALUE,
    HOUR(t.TRANSACTION_TIMESTAMP) AS TXN_HOUR,
    CASE WHEN HOUR(t.TRANSACTION_TIMESTAMP) BETWEEN 0 AND 5 THEN 1 ELSE 0 END AS IS_LATE_NIGHT,
    CASE WHEN DAYOFWEEK(t.TRANSACTION_TIMESTAMP) IN (0, 6) THEN 1 ELSE 0 END AS IS_WEEKEND,
    -- Add encoded features (simplified - using defaults)
    0 AS CHANNEL_ENCODED,
    0 AS TXN_TYPE_ENCODED,
    0 AS TXNS_LAST_24H,
    0 AS TXNS_LAST_1H,
    0 AS AMOUNT_LAST_24H,
    0 AS CUST_AVG_AMOUNT,
    0 AS CUST_STDDEV_AMOUNT,
    0 AS AMOUNT_ZSCORE,
    500 AS CREDIT_SCORE,
    5 AS CUSTOMER_TENURE_YEARS,
    0 AS RISK_RATING_ENCODED,
    0 AS CUST_PRIOR_FRAUD
FROM FSI_DEMO.RAW_BANKING.TRANSACTION_STAGING t
WHERE t.TRANSACTION_TIMESTAMP >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
LIMIT 1000
"""

print("Loading recent transactions from TRANSACTION_STAGING...")
staging_df = session.sql(staging_query).to_pandas()

if len(staging_df) > 0:
    print(f"✓ Loaded {len(staging_df):,} recent transactions")
    
    # Score staging transactions
    staging_keys = staging_df['TRANSACTION_KEY']
    staging_X = staging_df[feature_cols].fillna(0)
    staging_proba = model.predict_proba(staging_X)[:, 1]
    staging_pred = (staging_proba > 0.5).astype(int)
    
    # Create results
    staging_results = pd.DataFrame({
        'TRANSACTION_KEY': staging_keys,
        'FRAUD_PROBABILITY': staging_proba,
        'FRAUD_PREDICTION': staging_pred,
        'MODEL_VERSION': MODEL_VERSION,
        'SCORED_AT': datetime.now()
    })
    
    high_risk = staging_results[staging_results['FRAUD_PROBABILITY'] > 0.5]
    print(f"✓ Scored staging transactions")
    print(f"  High risk (>0.5): {len(high_risk):,} transactions\n")
    
    if len(high_risk) > 0:
        print("High Risk Transactions:")
        print(high_risk.head(10).to_string(index=False))
else:
    print("No recent transactions found in staging\n")

# Summary
print("\n" + "=" * 80)
print("TRAINING COMPLETE")
print("=" * 80)
print(f"Model Version: {MODEL_VERSION}")
print(f"Model Path: {model_path}")
print(f"AUC-ROC: {auc_score:.4f}")
print(f"Predictions written to: FSI_DEMO.ANALYTICS_BANKING.ML_FRAUD_SCORES")
print("=" * 80)

session.close()