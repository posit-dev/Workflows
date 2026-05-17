# FSI Demo - Financial Services Analytics & ML

A hands-on demonstration of financial services analytics using Snowflake, Python, R, and Posit tools. Follow along to build fraud detection models, credit risk assessments, and customer analytics dashboards.

**Note**: This demo provides the code framework and workflows. You'll need to either generate synthetic data using the provided simulation scripts or adapt the code to work with your own financial services data.

---

## 🎯 What You'll Build

This demo walks you through a complete financial services ML workflow:

1. **Fraud Detection Model** (Python) - Train and deploy a real-time fraud scoring API
2. **Credit Risk Assessment** (R) - Build credit risk models using tidymodels
3. **Customer Churn Prediction** (R) - Predict customer churn with machine learning
4. **Interactive Dashboards** - Create Python and Shiny dashboards for business users
5. **Automated Reports** - Generate executive reports with Quarto

---

## 📁 Project Structure

```
fsi_demo/
├── data/                          # Your data goes here (not included)
│   ├── accounts.csv/rds          # Account master data
│   ├── customers.csv/rds         # Customer information
│   ├── transactions.csv/rds      # Transaction records
│   ├── addresses.csv/rds         # Customer addresses
│   ├── branches.csv/rds          # Branch information
│   └── customer_analytics.csv/rds # Aggregated analytics
│
├── data_simulation/               # Scripts to generate synthetic data
│
├── scripts/                       # Core ML and data processing scripts
│   ├── 01_data_preparation.R     # Data prep and feature engineering (R)
│   ├── 02_train_fraud_model.py   # Fraud detection model training (Python)
│   ├── 03_score_new_transactions.py # FastAPI scoring service
│   ├── 03_credit_risk_model.R    # Credit risk modeling (R)
│   ├── 04_customer_churn_model.R # Churn prediction (R)
│   ├── fraud_scoring_scheduler.py # Scheduled scoring jobs
│   └── fraud_scoring.ipynb       # Interactive fraud analysis
│
├── models/                        # Trained models and analysis documents
│   ├── artifacts/                # Saved model files (.pkl)
│   ├── churn_model.rds           # Customer churn model
│   ├── credit_risk_model.rds     # Credit risk model
│   ├── fraud_detection.qmd       # Fraud detection analysis
│   ├── churn_prediction.qmd      # Churn analysis
│   └── customer_segmentation.qmd # Segmentation analysis
│
├── reports/                       # Quarto reports and dashboards
│   ├── fsi_executive_report.qmd  # Executive summary report
│   ├── monthly_executive.qmd     # Monthly business review
│   └── weekly_risk_fraud.qmd     # Risk and fraud monitoring
│
├── dashboards/                    # Python dashboards
│   └── app.py                    # Main dashboard application
│
├── shiny_apps/                    # R Shiny applications
│   └── customer_analytics/       # Customer analytics dashboard
│       └── app.R
│
├── quarto_docs/                   # Additional Quarto documentation
│
├── outputs/                       # Generated outputs and artifacts
│
├── .env.example                   # Environment variable template
├── requirements.txt               # Python dependencies
├── renv.lock                      # R package dependencies
└── _publish.yml                   # Posit Connect publishing config
```

---

## 🚀 Setup Instructions

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd fsi_demo
```

### Step 2: Install Dependencies

**Python**:
```bash
pip install -r requirements.txt
```

**R** (in R console):
```r
renv::restore()
```

### Step 3: Set Up Your Data

**Option A: Generate Synthetic Data**

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your Snowflake credentials:
   ```
   SNOWFLAKE_ACCOUNT=your-account
   SNOWFLAKE_USER=your-username
   SNOWFLAKE_PASSWORD=your-password
   SNOWFLAKE_WAREHOUSE=DEFAULT_WH
   SNOWFLAKE_DATABASE=FSI_DEMO
   SNOWFLAKE_SCHEMA=RAW_BANKING
   ```

3. Ensure your Snowflake database has the required tables (see Data Schema section below)

**Option B: Adapt to Your Own Data**

Modify the scripts to work with your existing data sources:
- Update file paths in scripts to point to your data
- Adjust column names and data types to match your schema
- Modify feature engineering logic as needed

---

## 📊 Data Schema

The demo expects the following data structure. Adapt your data or generate synthetic data to match:

### Required Tables/Files

**transactions** - Transaction records
- `transaction_id`: Unique transaction identifier
- `account_id`: Account identifier
- `customer_id`: Customer identifier
- `transaction_date`: Date/timestamp
- `amount`: Transaction amount
- `transaction_type`: Type of transaction (debit, credit, transfer, etc.)
- `is_fraud`: Fraud label (0/1) - for training data

**customers** - Customer information
- `customer_id`: Unique customer identifier
- `customer_name`: Customer name
- `age`: Customer age
- `income`: Annual income
- `credit_score`: Credit score
- `account_tenure_months`: Months as customer

**accounts** - Account master data
- `account_id`: Unique account identifier
- `customer_id`: Customer identifier
- `account_type`: Type of account (checking, savings, etc.)
- `balance`: Current balance
- `open_date`: Account opening date

**addresses** (optional) - Customer addresses
- `customer_id`: Customer identifier
- `city`, `state`, `zip_code`: Location information

**branches** (optional) - Branch information
- `branch_id`: Branch identifier
- `branch_name`: Branch name
- `region`: Geographic region

---

## 📚 Follow-Along Guide

### Tutorial 1: Fraud Detection (Python)

**Time: 20-30 minutes**

**Prerequisites**: Ensure you have transaction data with fraud labels

1. **Explore the data**:
   ```python
   import pandas as pd
   # Adjust path to your data source
   transactions = pd.read_csv('data/transactions.csv')
   transactions.head()
   ```

2. **Train the fraud model**:
   ```bash
   python scripts/02_train_fraud_model.py
   ```
   
   This script:
   - Loads transaction data from Snowflake or local files
   - Engineers features (transaction velocity, amount patterns, etc.)
   - Trains a Random Forest classifier
   - Saves the model to `models/artifacts/`
   
   **Note**: You may need to modify the script to match your data schema

3. **Score new transactions**:
   ```bash
   python scripts/03_score_new_transactions.py
   ```
   
   This creates a FastAPI endpoint for real-time fraud scoring.

4. **Explore interactively**:
   Open `scripts/fraud_scoring.ipynb` in Positron to experiment with the model.

**Key Learning**: Building production-ready ML pipelines with scikit-learn and FastAPI

---

### Tutorial 2: Credit Risk Modeling (R)

**Time: 15-20 minutes**

**Prerequisites**: Customer and account data with credit risk indicators

1. **Open the script**:
   ```r
   # In Positron, open scripts/03_credit_risk_model.R
   ```

2. **Adapt to your data**:
   - Update data loading code to point to your data source
   - Adjust column names as needed
   - Modify feature engineering for your use case

3. **Run the analysis**:
   ```r
   source("scripts/03_credit_risk_model.R")
   ```
   
   This script demonstrates:
   - Feature engineering with dplyr
   - Model training with tidymodels
   - Model evaluation and validation
   - Saving models with vetiver

4. **Review the Quarto document**:
   Open `models/fraud_detection.qmd` to see the full analysis with narrative.

**Key Learning**: Using tidymodels for credit risk assessment

---

### Tutorial 3: Customer Churn Prediction (R)

**Time: 15-20 minutes**

**Prerequisites**: Customer analytics data with churn indicators

1. **Adapt the script**:
   - Open `scripts/04_customer_churn_model.R`
   - Update data paths and column names
   - Adjust features based on your customer data

2. **Run the churn model**:
   ```r
   source("scripts/04_customer_churn_model.R")
   ```

**Key Learning**: Predicting customer behavior with machine learning

---

### Tutorial 3.5: Deploy Fraud Model to Posit Connect

**Time: 10-15 minutes**

**Prerequisites**: 
- Completed Tutorial 1 (trained fraud model exists in `models/artifacts/`)
- Posit Connect account with API key
- `rsconnect-python` installed (`pip install rsconnect-python`)

Now that you've trained your fraud detection model, deploy it as a production FastAPI service that your organization can use for real-time fraud scoring.

#### 1. Verify Your FastAPI Application

Open `scripts/03_score_new_transactions.py` and ensure it's structured as a FastAPI app:

```python
from fastapi import FastAPI
import joblib
import pandas as pd
from pydantic import BaseModel

app = FastAPI(title="Fraud Detection API")

# Load model at startup
model = joblib.load("models/artifacts/fraud_model.pkl")

class Transaction(BaseModel):
    amount: float
    transaction_type: str
    hour_of_day: int
    day_of_week: int
    # Add other features your model expects

@app.post("/predict")
async def predict_fraud(transaction: Transaction):
    # Convert to DataFrame for model
    features = pd.DataFrame([transaction.dict()])
    prediction = model.predict_proba(features)
    
    return {
        "fraud_probability": float(prediction[0][1]),
        "is_fraud": bool(prediction[0][1] > 0.5)
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": "fraud_detection_v1"}
```

**Note**: Adapt the `Transaction` model fields to match your trained model's features.

#### 2. Test Locally First

Before deploying, verify the API works on your machine:

```bash
# Start the FastAPI server
uvicorn scripts.03_score_new_transactions:app --reload
```

In another terminal or Python console, test it:

```python
import requests

response = requests.post(
    "http://localhost:8000/predict",
    json={
        "amount": 1500.00,
        "transaction_type": "debit",
        "hour_of_day": 23,
        "day_of_week": 6
    }
)
print(response.json())
```

#### 3. Deploy to Posit Connect

**Option A: Using Positron's Publish Button** (Easiest)

1. Open `scripts/03_score_new_transactions.py` in Positron
2. Click the **Publish** button (📤) in the top-right corner
3. Select **Posit Connect** as the destination
4. Choose your Connect server (or add a new one)
5. Configure:
   - **Title**: "Fraud Detection API"
   - **Access**: Set who can view/execute
6. Click **Publish**

Positron will automatically:
- Package your code and dependencies
- Upload to Connect
- Configure the FastAPI application
- Provide you with the deployment URL

**Option B: Using rsconnect-python CLI**

```bash
# From your project root directory
rsconnect deploy fastapi \
  --server https://connect.your-company.com \
  --api-key YOUR_API_KEY \
  --title "Fraud Detection API" \
  --entrypoint scripts.03_score_new_transactions:app \
  .
```

**Option C: Using Python Code**

```python
from rsconnect.api import RSConnectClient

# Connect to your server
client = RSConnectClient(
    api_key="YOUR_API_KEY",
    url="https://connect.your-company.com"
)

# Deploy the application
client.deploy(
    name="fraud-detection-api",
    title="Fraud Detection API",
    entrypoint="scripts.03_score_new_transactions:app"
)
```

#### 4. Configure Your Deployment on Connect

After deployment, configure your API through the Connect dashboard:

1. **Access Control**: 
   - Set viewer permissions (who can see the API docs)
   - Set publisher permissions (who can update the API)
   - Configure API key requirements for consumers

2. **Environment Variables** (if needed):
   - Add Snowflake credentials for live data access
   - Set model version or configuration flags
   - Add any API keys for external services

3. **Runtime Settings**:
   - Adjust memory allocation (e.g., 2GB for model loading)
   - Set timeout limits for predictions
   - Configure number of worker processes

4. **Vanity URL** (optional):
   - Create a friendly URL like `/fraud-api/` instead of `/content/abc123/`

#### 5. Test Your Deployed API

Once deployed, Connect provides you with a URL. Test it:

```python
import requests

# Replace with your actual Connect URL
api_url = "https://connect.your-company.com/content/abc123/predict"

# Test transaction
test_data = {
    "amount": 2500.00,
    "transaction_type": "withdrawal",
    "hour_of_day": 2,
    "day_of_week": 0
}

response = requests.post(
    api_url,
    json=test_data,
    headers={"Authorization": f"Key YOUR_API_KEY"}
)

print(f"Fraud Probability: {response.json()['fraud_probability']:.2%}")
print(f"Flagged as Fraud: {response.json()['is_fraud']}")


#### 6. Share with Your Team

Your fraud detection API is now live! Share it with:

- **Data Engineers**: To integrate into transaction pipelines
- **Application Developers**: To add fraud checks to banking apps
- **Analysts**: To score historical transactions in batch

Connect automatically generates **interactive API documentation** at:
```
https://connect.your-company.com/content/abc123/__docs__/
```

#### 7. Monitor and Update

**View Logs**:
- Access logs through the Connect dashboard
- Monitor API usage, response times, and errors
- Set up email alerts for failures

**Update Your Model**:
When you retrain your model with new data:

```bash
# Retrain the model
python scripts/02_train_fraud_model.py

# Redeploy (updates existing deployment)
rsconnect deploy fastapi \
  --server https://connect.your-company.com \
  --api-key YOUR_API_KEY \
  --app-id abc123 \
  .
```

Or simply click **Publish** again in Positron to update the existing deployment.

**Version Control**:
Connect maintains deployment history, so you can:
- Roll back to previous versions if needed
- Compare performance across model versions
- Track when models were updated

#### Tips for Production Deployment

- **Model Versioning**: Include version info in your health check endpoint
- **Input Validation**: Use Pydantic models to validate incoming data
- **Error Handling**: Add try/except blocks for graceful failures
- **Logging**: Log predictions for audit trails and model monitoring
- **Rate Limiting**: Configure on Connect to prevent abuse
- **Monitoring**: Set up alerts for prediction drift or errors

**Key Learning**: Deploying production ML APIs with enterprise governance, monitoring, and easy updates

---

### Tutorial 4: Build Dashboards

**Python Dashboard** (15 minutes):
```bash
cd dashboards
# Update app.py to point to your data
python app.py
```

Open your browser to view the interactive dashboard.

**R Shiny Dashboard** (15 minutes):
```r
# Update data paths in shiny_apps/customer_analytics/app.R
shiny::runApp("shiny_apps/customer_analytics")
```

**Key Learning**: Creating interactive data applications for stakeholders

---

### Tutorial 5: Generate Reports

**Time: 10 minutes**

Render professional reports with Quarto:

```bash
# Executive summary
quarto render reports/fsi_executive_report.qmd

# Weekly risk report
quarto render reports/weekly_risk_fraud.qmd
```

**Note**: Update report templates to reference your data sources

**Key Learning**: Automated, reproducible reporting

---

## 🔧 Working with the Data

### Snowflake Setup

If using Snowflake, create tables matching the schema above:

```sql
-- Example table structure
CREATE TABLE FSI_DEMO.RAW_BANKING.TRANSACTION_STAGING (
    transaction_id VARCHAR,
    account_id VARCHAR,
    customer_id VARCHAR,
    transaction_date TIMESTAMP,
    amount DECIMAL(18,2),
    transaction_type VARCHAR,
    is_fraud INTEGER
);
```

Expected tables:
- `FSI_DEMO.RAW_BANKING.TRANSACTION_STAGING`: Incoming transactions
- `FSI_DEMO.ANALYTICS_BANKING.ML_FRAUD_SCORES`: Fraud predictions
- `CIF_CUSTOMER_MASTER`: Customer demographics
- `CBS_ACCOUNT_MASTER`: Account details

### Local Files

Store your data in the `data/` directory:
- **CSV format**: For Python (pandas, polars)
- **RDS format**: For R (readRDS)

Example loading data:

**Python**:
```python
import pandas as pd
df = pd.read_csv('data/transactions.csv')
```

**R**:
```r
library(readr)
df <- read_csv("data/transactions.csv")
# Or for RDS files:
df <- readRDS("data/transactions.rds")
```

---

## 💡 Tips for Following Along

### Start Simple
- Begin with Tutorial 1 (Fraud Detection)
- Generate synthetic data first to understand the workflow
- Adapt one script at a time to your own data

### Experiment
- Modify hyperparameters in the model training scripts
- Try different feature engineering approaches
- Customize the dashboards with your own visualizations

### Use Positron Features
- **Variables pane**: Inspect data frames and model objects
- **Plots pane**: View visualizations as you create them
- **Console**: Test code snippets interactively
- **Help pane**: Access R and Python documentation

### Adapting to Your Data

**Common modifications needed**:
1. Update column names throughout scripts
2. Adjust data types and formats
3. Modify feature engineering logic
4. Update SQL queries for your schema
5. Change file paths and connection strings

**Workflow**:
1. Load your data in console
2. Explore structure and column names
3. Update script variables and column references
4. Test transformations interactively
5. Run full script once validated

---

## 🐛 Troubleshooting

### "Module not found" or "Package not found"

**Python**:
```bash
pip install --upgrade -r requirements.txt
```

**R**:
```r
renv::restore()
```

### Data Schema Mismatches

- Check column names in your data vs. script expectations
- Use `df.columns` (Python) or `names(df)` (R) to inspect
- Update scripts to match your schema
- Consider creating a data mapping/transformation layer



### Snowflake Connection Issues

- Verify credentials in `.env`
- Test connection in console first
- Check network access and firewall rules
- Verify table and schema names

### Memory Issues

- Use `LIMIT` in SQL queries during development
- Sample large datasets: `df.sample(n=10000)` (Python) or `slice_sample(df, n=10000)` (R)
- Close unused data frames
- Process data in chunks for large datasets

### Script Errors

- Check that you're in the correct working directory
- Ensure all dependencies are installed
- Verify data files exist or connections work
- Review error messages for missing columns or data type issues

---

## 📚 Additional Resources

- [Positron Documentation](https://positron.posit.co/)
- [Posit Connect User Guide](https://docs.posit.co/connect/)
- [Quarto Documentation](https://quarto.org/)
- [Snowflake Python Connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector)
- [Tidymodels Documentation](https://www.tidymodels.org/)

---

## 🎓 Demo Scenarios

### Quick Demo (5 minutes)
1. Show data generation or connection
2. Run fraud scoring script
3. Display results in dashboard
4. Show deployed API on Connect

### Technical Deep Dive (15 minutes)
1. Walk through data preparation
2. Explain model training process
3. Show feature engineering
4. Demonstrate API deployment
5. Review monitoring and versioning

### Business Value Focus (10 minutes)
1. Emphasize time-to-production
2. Highlight enterprise governance
3. Show API accessibility
4. Demonstrate cost savings

---

## 🤝 Contributing

This is a demonstration project. For questions or issues, contact your Posit representative.

---

## 📄 License

See LICENSE file for details.
