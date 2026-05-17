"""
Score new transactions for fraud using the trained model
Deployable as a FastAPI app on Posit Connect (scheduled or on-demand)
"""
import os
import pandas as pd
from snowflake.snowpark import Session
import pickle
from datetime import datetime, timedelta
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Fraud Scoring Engine", version="1.0.0")


def get_session():
    """Get Snowflake session with automatic fallback"""
    sf_home = os.getenv("SNOWFLAKE_HOME", "")

    if sf_home:
        try:
            session = Session.builder.configs({
                "connection_name": "workbench",
                "database": "FSI_DEMO",
                "schema": "RAW_BANKING",
            }).create()
            return session
        except Exception:
            pass

    token = os.getenv("SNOWFLAKE_TOKEN")
    if token:
        try:
            session = Session.builder.configs({
                "account": os.getenv("SNOWFLAKE_ACCOUNT", "os.getenv("SNOWFLAKE_ACCOUNT", "your-account")"),
                "token": token,
                "authenticator": "oauth",
                "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH"),
                "database": "FSI_DEMO",
                "schema": "RAW_BANKING",
            }).create()
            return session
        except Exception:
            pass

    raise RuntimeError(
        "Could not connect to Snowflake. "
        "Set SNOWFLAKE_TOKEN environment variable with a fresh OAuth token."
    )


class SessionPool:
    def __init__(self):
        self.session = None
        self.last_refresh = None
        self.refresh_interval = timedelta(minutes=25)

    def get_session(self):
        now = datetime.now()
        if (self.session is None or
            self.last_refresh is None or
            now - self.last_refresh > self.refresh_interval):
            if self.session:
                try:
                    self.session.close()
                except Exception:
                    pass
            self.session = get_session()
            self.last_refresh = now
        return self.session


session_pool = SessionPool()


def engineer_fraud_features(df):
    df['TRANSACTION_TIMESTAMP'] = pd.to_datetime(df['TRANSACTION_TIMESTAMP'])
    df['TXN_HOUR'] = df['TRANSACTION_TIMESTAMP'].dt.hour
    df['IS_WEEKEND'] = df['TRANSACTION_TIMESTAMP'].dt.dayofweek >= 5

    df['IS_HIGH_VALUE'] = (df['TRANSACTION_AMOUNT'] > 5000).astype(int)
    df['IS_LATE_NIGHT'] = df['TXN_HOUR'].between(0, 5).astype(int)

    txn_type_map = {'DEBIT': 0, 'CREDIT': 1, 'TRANSFER': 2, 'WITHDRAWAL': 3, 'DEPOSIT': 4, 'PAYMENT': 5}
    df['TXN_TYPE_ENCODED'] = df['TRANSACTION_TYPE'].map(txn_type_map).fillna(0)

    channel_map = {'Online Banking': 0, 'Mobile App': 1, 'ATM': 2, 'Branch': 3, 'Point of Sale': 4}
    df['CHANNEL_ENCODED'] = df['CHANNEL_NAME'].map(channel_map).fillna(0)

    df['CREDIT_SCORE'] = 700
    df['CUSTOMER_TENURE_YEARS'] = 5
    df['RISK_RATING_ENCODED'] = 1

    df = df.sort_values(['ACCOUNT_NUMBER', 'TRANSACTION_TIMESTAMP'])

    df['TXNS_LAST_24H'] = df.groupby('ACCOUNT_NUMBER').cumcount() + 1
    df['TXNS_LAST_1H'] = 1
    df['AMOUNT_LAST_24H'] = df.groupby('ACCOUNT_NUMBER')['TRANSACTION_AMOUNT'].cumsum()

    df['CUST_AVG_AMOUNT'] = df.groupby('ACCOUNT_NUMBER')['TRANSACTION_AMOUNT'].transform('mean')
    df['CUST_STDDEV_AMOUNT'] = df.groupby('ACCOUNT_NUMBER')['TRANSACTION_AMOUNT'].transform('std').fillna(0)
    df['AMOUNT_ZSCORE'] = ((df['TRANSACTION_AMOUNT'] - df['CUST_AVG_AMOUNT']) /
                           (df['CUST_STDDEV_AMOUNT'] + 0.01))

    return df


def score_batch():
    session = session_pool.get_session()

    model_dir = os.path.expanduser('~/snowflake_demos/fsi_demo/models/artifacts')
    if not os.path.isdir(model_dir):
        model_dir = os.path.join(os.path.dirname(__file__), 'models')

    model_files = sorted([f for f in os.listdir(model_dir) if f.startswith('fraud_model_') and f.endswith('.pkl')])

    if not model_files:
        return {"scored": 0, "error": f"No models found in {model_dir}"}

    model_path = os.path.join(model_dir, model_files[-1])

    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
        model = model_data['model']

    unscored = session.sql("""
        SELECT t.*
        FROM FSI_DEMO.RAW_BANKING.TRANSACTION_STAGING t
        LEFT JOIN FSI_DEMO.ANALYTICS_BANKING.ML_FRAUD_SCORES s
            ON t.TRANSACTION_ID = s.TRANSACTION_KEY
        WHERE s.TRANSACTION_KEY IS NULL
        ORDER BY t.TRANSACTION_TIMESTAMP DESC
        LIMIT 100
    """).to_pandas()

    if unscored.empty:
        return {"scored": 0, "message": "No new transactions to score"}

    features_df = engineer_fraud_features(unscored)

    available_features = [f for f in model.feature_names_in_ if f in features_df.columns]

    if len(available_features) != len(model.feature_names_in_):
        missing = set(model.feature_names_in_) - set(available_features)
        return {"scored": 0, "error": f"Missing features: {missing}"}

    X = features_df[available_features]
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)[:, 1]

    results = pd.DataFrame({
        'TRANSACTION_KEY': features_df['TRANSACTION_ID'],
        'FRAUD_PROBABILITY': probabilities,
        'FRAUD_PREDICTION': predictions.astype(bool),
        'MODEL_VERSION': 'v1.0',
        'SCORED_AT': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    }).reset_index(drop=True)

    session.write_pandas(
        results,
        table_name='ML_FRAUD_SCORES',
        database='FSI_DEMO',
        schema='ANALYTICS_BANKING',
        auto_create_table=False
    )

    return {"scored": len(results), "model": model_files[-1]}


class ScoreResponse(BaseModel):
    scored: int
    model: str = ""
    message: str = ""
    error: str = ""


@app.get("/")
def health():
    return {"status": "ok", "service": "fraud-scoring-engine"}


@app.post("/score", response_model=ScoreResponse)
def run_scoring():
    result = score_batch()
    return ScoreResponse(**result)


@app.get("/score", response_model=ScoreResponse)
def run_scoring_get():
    result = score_batch()
    return ScoreResponse(**result)
