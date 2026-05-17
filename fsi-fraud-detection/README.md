# FSI Demo: Orbital ML Deployment to Snowflake

## 🎯 Demo Overview

This demonstration showcases the **seamless integration between Posit's R ecosystem and Snowflake** for end-to-end machine learning workflows in financial services. Using the `orbital` package, we deploy tidymodels directly into Snowflake as native SQL functions, enabling **in-database predictions at scale**.

---

## 🚀 Quick Start

### Prerequisites
```r
# Install required packages
install.packages(c("DBI", "odbc", "dplyr", "tidymodels", "orbital", "xgboost"))
```

### Environment Setup
Create `.Renviron` file in your project root with your Snowflake credentials:
```
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=FSI_DEMO
SNOWFLAKE_SCHEMA=RAW_BANKING
```

### Run the Demo
```r
# 1. Set up data and connection
source("scripts/00_setup.R")

# 2. Prepare banking data
source("scripts/01_data_preparation.R")

# 3. Build ML models locally
source("scripts/02_ml_models.R")

# 4. Deploy to Snowflake with orbital
source("scripts/04_orbital_deployment_live.R")
```

---

## 🎤 Demo Script & Talking Points

### **Opening: The Challenge** (2 minutes)

> *"Financial institutions face a critical challenge: How do you operationalize machine learning models at scale while keeping sensitive data secure and compliant?"*

**Key Points:**
- Traditional ML deployment requires moving data out of the data warehouse
- Data movement creates security risks, compliance issues, and latency
- Data scientists work in R/Python, but production systems need SQL
- Models often become stale or inconsistent between environments

**Transition:** *"Today I'll show you how Posit and Snowflake solve this together with a real FSI use case."*

---

### **Act 1: Data Science in R** (5 minutes)

#### **Scene 1: Connect to Live Data**
```r
# Show connection to Snowflake
source("scripts/00_setup.R")
```

**Talking Points:**
- *"Data scientists work where they're productive - in R and Python"*
- *"But they need access to live, production data in Snowflake"*
- *"Notice we're pulling millions of customer records directly from Snowflake"*

#### **Scene 2: Feature Engineering**
```r
# Show data preparation
source("scripts/01_data_preparation.R")
```

**Talking Points:**
- *"This is real banking data - customers, accounts, transactions"*
- *"We're creating features like customer tenure, account balances, product holdings"*
- *"All the feature engineering happens in R using familiar dplyr syntax"*

#### **Scene 3: Model Training**
```r
# Show model building
source("scripts/02_ml_models.R")
```

**Talking Points:**
- *"We're building a churn prediction model using tidymodels"*
- *"XGBoost classifier with proper cross-validation and hyperparameter tuning"*
- *"This is production-quality ML, not just a prototype"*

**Key Demo Moment:** Show model performance metrics
- *"92% accuracy on holdout data - this model is ready for production"*

---

### **Act 2: The Magic of Orbital** (7 minutes)

#### **Scene 1: The Traditional Problem**
> *"Normally, this is where things get complicated. How do you deploy this R model to production? Typically you'd need to:"*
- Rewrite the model in SQL or Python
- Set up model serving infrastructure  
- Create APIs and batch scoring jobs
- Manage model versioning and updates
- Handle data movement and security

#### **Scene 2: The Orbital Solution**
```r
# Show orbital deployment
orbital_obj <- orbital(churn_fit)
orbital_snowflake_udf(orbital_obj, connection = conn, name = "PREDICT_CUSTOMER_CHURN")
```

**Key Talking Points:**
- *"With orbital, we deploy the EXACT same model that we trained in R"*
- *"No translation, no rewriting, no approximation"*
- *"The model becomes a native Snowflake SQL function"*
- *"Zero data movement - predictions happen inside Snowflake"*

#### **Scene 3: Predictions at Scale**
```sql
-- Show SQL predictions
SELECT customer_id, 
       PREDICT_CUSTOMER_CHURN(age, tenure, balance, ...) as churn_score
FROM customers;
```

**Wow Moments:**
- *"This is the same model we trained in R, now running as SQL"*
- *"Any SQL user, BI tool, or application can call this function"*
- *"Snowflake's compute scales this to millions of predictions per second"*

---

### **Act 3: Production Impact** (4 minutes)

#### **Scene 1: Real-time Insights**
```r
# Show prediction results
dbGetQuery(conn, "SELECT * FROM CUSTOMER_CHURN_PREDICTIONS LIMIT 10")
```

**Business Impact:**
- *"Marketing can now target high-risk customers in real-time"*
- *"Customer service gets churn alerts during calls"*
- *"Risk management has up-to-date portfolio views"*

#### **Scene 2: Operational Excellence**
**Show the predictions table:**
- Automated scoring of entire customer base
- Risk segmentation (High/Medium/Low)
- Timestamp tracking for model governance

**Key Points:**
- *"This runs on Snowflake's schedule - daily, hourly, or real-time"*
- *"No separate ML infrastructure to maintain"*
- *"Automatic scaling with your data volume"*

---

## 🤝 Better Together: Snowflake + Posit Value Story

### **For Data Scientists**
- **Familiar Tools**: Work in R/Python with full ecosystem
- **Live Data Access**: Connect directly to Snowflake without copies
- **Rapid Iteration**: Train and deploy models in the same workflow
- **No Translation**: Deploy exact models without rewriting

### **For Data Engineers**
- **Zero ETL**: No data movement for predictions
- **Native Integration**: Models become SQL functions
- **Automatic Scaling**: Leverage Snowflake compute
- **Simple Governance**: Models versioned and tracked in Snowflake

### **For IT/Security**
- **Data Stays Put**: No sensitive data leaves Snowflake
- **Compliance Ready**: Leverage existing Snowflake security
- **Reduced Infrastructure**: No separate ML serving layer
- **Audit Trail**: All predictions logged and traceable

### **For Business Users**
- **SQL Access**: Use models in any BI tool or dashboard
- **Real-time Insights**: Predictions available immediately
- **Consistent Results**: Same model everywhere
- **Faster Time-to-Value**: Days not months to production

---

## 🔧 Technical Architecture

### **Data Flow**
```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Snowflake │───▶│  R/Positron  │───▶│   Snowflake     │
│  (Raw Data) │    │ (Train Model)│    │ (Deploy & Score)│
└─────────────┘    └──────────────┘    └─────────────────┘
```

### **Key Technologies**
- **Snowflake**: Data warehouse, compute, and model hosting
- **Positron**: Integrated development environment
- **R + tidymodels**: Model development and training
- **orbital**: Model deployment and translation
- **DBI/odbc**: Secure database connectivity

### **Model Deployment Process**
1. **Extract**: Pull training data from Snowflake
2. **Transform**: Feature engineering in R
3. **Train**: Build model with tidymodels
4. **Deploy**: Convert to SQL with orbital
5. **Score**: Run predictions in Snowflake
6. **Monitor**: Track performance and drift

---

## 📊 Demo Data Schema

### **Tables Used**
- `CIF_CUSTOMER_MASTER`: Customer demographics and profiles
- `CBS_ACCOUNT_MASTER`: Account details and balances  
- `CIF_CUSTOMER_ADDRESS`: Customer location data

### **Generated Outputs**
- `CUSTOMER_CHURN_PREDICTIONS`: Scored customer base with risk levels
- `PREDICT_CUSTOMER_CHURN()`: Deployable SQL function

---

## 🎯 Demo Variations

### **Quick Demo (5 minutes)**
- Show connection to Snowflake
- Run orbital deployment
- Execute SQL predictions
- Highlight zero data movement

### **Technical Deep Dive (15 minutes)**
- Walk through model training process
- Explain orbital internals
- Show performance comparisons
- Discuss governance and monitoring

### **Business Value Focus (10 minutes)**
- Emphasize time-to-production
- Highlight security and compliance
- Show cost savings from no data movement
- Demonstrate business user accessibility

---

## 🔍 Troubleshooting

### **Common Issues**
1. **Connection Errors**: Check `.Renviron` credentials
2. **Package Installation**: Ensure orbital and tidymodels are latest versions
3. **Memory Issues**: Use `collect()` sparingly with large datasets
4. **SQL Errors**: Verify Snowflake permissions for UDF creation

### **Performance Tips**
- Use `dbplyr` for large data transformations
- Limit training data size for faster iteration
- Consider feature selection for model efficiency
- Monitor Snowflake warehouse usage during deployment

---

## 📚 Additional Resources

- [Orbital Package Documentation](https://orbital.tidymodels.org/)
- [Snowflake + R Integration Guide](https://docs.snowflake.com/en/user-guide/r-connector)
- [Tidymodels Documentation](https://www.tidymodels.org/)
- [Positron IDE](https://positron.posit.co/)

---

## 🏆 Key Demo Takeaways

### **Technical Excellence**
- Seamless R-to-SQL model deployment
- Production-ready ML in minutes, not months
- Zero-copy architecture for security and performance

### **Business Value**
- Faster time-to-market for ML initiatives
- Reduced infrastructure costs and complexity
- Enhanced data security and compliance

### **Partnership Strength**
- Best-in-class tools working together
- Unified workflow from development to production
- Scalable solution for enterprise ML needs

---

*"This is the future of enterprise machine learning - where data scientists can focus on building great models, and those models seamlessly become part of your data infrastructure."*