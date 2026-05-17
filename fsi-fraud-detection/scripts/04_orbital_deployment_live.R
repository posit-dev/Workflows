# FSI Demo - Orbital Deployment to Snowflake (Live Data)
# This script demonstrates using the orbital package to deploy tidymodels
# workflows to Snowflake for in-database predictions
# 
# Reference: https://www.snowflake.com/en/developers/guides/tidymodel-prediction-workflows-inside-snowflake-with-orbital/

library(DBI)
library(dplyr)
library(tidymodels)
library(orbital)
library(xgboost)

# ============================================================================
# 1. CONNECT TO SNOWFLAKE
# ============================================================================

message("Connecting to Snowflake...")

# Use existing connection or create new one
if (!exists("conn")) {
  conn <- dbConnect(
    odbc::odbc(),
    Driver = "Snowflake",
    Server = paste0(Sys.getenv("SNOWFLAKE_ACCOUNT"), ".snowflakecomputing.com"),
    UID = Sys.getenv("SNOWFLAKE_USER"),
    PWD = Sys.getenv("SNOWFLAKE_PASSWORD"),
    Warehouse = Sys.getenv("SNOWFLAKE_WAREHOUSE"),
    Database = Sys.getenv("SNOWFLAKE_DATABASE"),
    Schema = Sys.getenv("SNOWFLAKE_SCHEMA")
  )
}

# Set context
dbExecute(conn, "USE WAREHOUSE DEFAULT_WH")
dbExecute(conn, "USE DATABASE FSI_DEMO")
dbExecute(conn, "USE SCHEMA RAW_BANKING")

# ============================================================================
# 2. PULL LIVE DATA FROM SNOWFLAKE
# ============================================================================

message("Pulling live data from Snowflake...")

# Pull customer and account data
customers <- dbGetQuery(conn, "SELECT * FROM FSI_DEMO.RAW_BANKING.CIF_CUSTOMER_MASTER")
accounts <- dbGetQuery(conn, "SELECT * FROM FSI_DEMO.RAW_BANKING.CBS_ACCOUNT_MASTER")
addresses <- dbGetQuery(conn, "SELECT * FROM FSI_DEMO.RAW_BANKING.CIF_CUSTOMER_ADDRESS WHERE IS_PRIMARY_ADDRESS = TRUE")

# Create analytical dataset
customer_data <- customers |>
  left_join(addresses, by = "CIF_NUMBER") |>
  left_join(
    accounts |> 
      group_by(CIF_NUMBER) |> 
      summarise(
        total_accounts = n(),
        total_balance = sum(CURRENT_BALANCE, na.rm = TRUE),
        avg_balance = mean(CURRENT_BALANCE, na.rm = TRUE),
        total_credit_limit = sum(CREDIT_LIMIT, na.rm = TRUE),
        has_savings = any(ACCOUNT_TYPE == "SAVINGS"),
        has_checking = any(ACCOUNT_TYPE == "CHECKING"),
        has_loan = any(ACCOUNT_TYPE == "LOAN"),
        .groups = "drop"
      ),
    by = "CIF_NUMBER"
  )

message(sprintf("Loaded %d customers from Snowflake", nrow(customer_data)))

# ============================================================================
# 3. PREPARE TRAINING DATA
# ============================================================================

message("Preparing training data...")

# Create synthetic churn labels for demonstration
# In production, you would use actual historical churn data
set.seed(123)
training_data <- customer_data |>
  mutate(
    # Calculate customer age and tenure
    customer_age = as.numeric(difftime(Sys.Date(), DATE_OF_BIRTH, units = "days")) / 365.25,
    account_tenure_days = as.numeric(difftime(Sys.Date(), CUSTOMER_SINCE_DATE, units = "days")),
    
    # Create synthetic churn label based on risk factors
    churn_risk_score = 
      (total_balance < 1000) * 0.3 +
      (total_accounts == 1) * 0.2 +
      (account_tenure_days < 180) * 0.3 +
      (!has_savings) * 0.1 +
      (customer_age < 25 | customer_age > 70) * 0.1,
    
    # Convert to binary outcome
    churned = if_else(churn_risk_score + runif(n()) * 0.3 > 0.5, 1, 0),
    churned = factor(churned, levels = c(0, 1), labels = c("No", "Yes"))
  ) |>
  select(
    CIF_NUMBER,
    churned,
    customer_age,
    account_tenure_days,
    total_accounts,
    total_balance,
    avg_balance,
    total_credit_limit,
    has_savings,
    has_checking,
    has_loan,
    GENDER,
    MARITAL_STATUS,
    CITY,
    STATE
  ) |>
  filter(!is.na(churned))

message(sprintf("Training data: %d customers, %d churned (%.1f%%)", 
                nrow(training_data), 
                sum(training_data$churned == "Yes"),
                100 * mean(training_data$churned == "Yes")))

# ============================================================================
# 4. BUILD AND TRAIN TIDYMODELS WORKFLOW
# ============================================================================

message("Building tidymodels workflow...")

# Split data
set.seed(456)
data_split <- initial_split(training_data, prop = 0.75, strata = churned)
train_data <- training(data_split)
test_data <- testing(data_split)

# Create recipe
churn_recipe <- recipe(churned ~ ., data = train_data) |>
  update_role(CIF_NUMBER, new_role = "ID") |>
  step_impute_median(all_numeric_predictors()) |>
  step_normalize(all_numeric_predictors()) |>
  step_dummy(all_nominal_predictors())

# Define model
xgb_spec <- boost_tree(
  trees = 100,
  tree_depth = 6,
  min_n = 5,
  learn_rate = 0.1
) |>
  set_engine("xgboost") |>
  set_mode("classification")

# Create workflow
churn_workflow <- workflow() |>
  add_recipe(churn_recipe) |>
  add_model(xgb_spec)

# Train model
message("Training model locally...")
churn_fit <- fit(churn_workflow, data = train_data)

# Evaluate on test set
test_predictions <- predict(churn_fit, test_data, type = "prob") |>
  bind_cols(test_data)

test_metrics <- test_predictions |>
  metrics(truth = churned, .pred_Yes)

message("Model performance on test set:")
print(test_metrics)

# ============================================================================
# 5. DEPLOY TO SNOWFLAKE USING ORBITAL
# ============================================================================

message("Deploying model to Snowflake using orbital...")

# Convert workflow to orbital object
orbital_obj <- orbital(churn_fit)

# Deploy as Snowflake UDF
# This creates a SQL function that can be called directly in Snowflake
orbital_snowflake_udf(
  orbital_obj,
  connection = conn,
  name = "PREDICT_CUSTOMER_CHURN",
  schema = "RAW_BANKING"
)

message("Model deployed as Snowflake UDF: RAW_BANKING.PREDICT_CUSTOMER_CHURN()")

# ============================================================================
# 6. CREATE PREDICTIONS TABLE IN SNOWFLAKE
# ============================================================================

message("Creating predictions table in Snowflake...")

# First, create a view with prepared features
dbExecute(conn, "
  CREATE OR REPLACE VIEW FSI_DEMO.RAW_BANKING.CUSTOMER_FEATURES AS
  SELECT 
    c.CIF_NUMBER,
    c.CUSTOMER_NAME,
    c.EMAIL,
    c.PHONE_NUMBER,
    DATEDIFF('day', c.DATE_OF_BIRTH, CURRENT_DATE()) / 365.25 as customer_age,
    DATEDIFF('day', c.CUSTOMER_SINCE_DATE, CURRENT_DATE()) as account_tenure_days,
    COALESCE(COUNT(a.ACCOUNT_NUMBER), 0) as total_accounts,
    COALESCE(SUM(a.CURRENT_BALANCE), 0) as total_balance,
    COALESCE(AVG(a.CURRENT_BALANCE), 0) as avg_balance,
    COALESCE(SUM(a.CREDIT_LIMIT), 0) as total_credit_limit,
    MAX(CASE WHEN a.ACCOUNT_TYPE = 'SAVINGS' THEN 1 ELSE 0 END) as has_savings,
    MAX(CASE WHEN a.ACCOUNT_TYPE = 'CHECKING' THEN 1 ELSE 0 END) as has_checking,
    MAX(CASE WHEN a.ACCOUNT_TYPE = 'LOAN' THEN 1 ELSE 0 END) as has_loan,
    c.GENDER,
    c.MARITAL_STATUS,
    addr.CITY,
    addr.STATE
  FROM FSI_DEMO.RAW_BANKING.CIF_CUSTOMER_MASTER c
  LEFT JOIN FSI_DEMO.RAW_BANKING.CBS_ACCOUNT_MASTER a ON c.CIF_NUMBER = a.CIF_NUMBER
  LEFT JOIN FSI_DEMO.RAW_BANKING.CIF_CUSTOMER_ADDRESS addr 
    ON c.CIF_NUMBER = addr.CIF_NUMBER AND addr.IS_PRIMARY_ADDRESS = TRUE
  GROUP BY c.CIF_NUMBER, c.CUSTOMER_NAME, c.EMAIL, c.PHONE_NUMBER,
           c.DATE_OF_BIRTH, c.CUSTOMER_SINCE_DATE, c.GENDER, c.MARITAL_STATUS, 
           addr.CITY, addr.STATE
")

message("Created feature view: FSI_DEMO.RAW_BANKING.CUSTOMER_FEATURES")

# Now create predictions table using the UDF
dbExecute(conn, "
  CREATE OR REPLACE TABLE FSI_DEMO.RAW_BANKING.CUSTOMER_CHURN_PREDICTIONS AS
  SELECT 
    CIF_NUMBER,
    CUSTOMER_NAME,
    EMAIL,
    PHONE_NUMBER,
    customer_age,
    account_tenure_days,
    total_accounts,
    total_balance,
    avg_balance,
    total_credit_limit,
    has_savings,
    has_checking,
    has_loan,
    GENDER,
    MARITAL_STATUS,
    CITY,
    STATE,
    PREDICT_CUSTOMER_CHURN(
      customer_age,
      account_tenure_days,
      total_accounts,
      total_balance,
      avg_balance,
      total_credit_limit,
      has_savings,
      has_checking,
      has_loan,
      GENDER,
      MARITAL_STATUS,
      CITY,
      STATE
    ) as churn_probability,
    CASE 
      WHEN PREDICT_CUSTOMER_CHURN(
        customer_age, account_tenure_days, total_accounts, total_balance,
        avg_balance, total_credit_limit, has_savings, has_checking, has_loan,
        GENDER, MARITAL_STATUS, CITY, STATE
      ) > 0.7 THEN 'High Risk'
      WHEN PREDICT_CUSTOMER_CHURN(
        customer_age, account_tenure_days, total_accounts, total_balance,
        avg_balance, total_credit_limit, has_savings, has_checking, has_loan,
        GENDER, MARITAL_STATUS, CITY, STATE
      ) > 0.4 THEN 'Medium Risk'
      ELSE 'Low Risk'
    END as risk_category,
    CURRENT_TIMESTAMP() as prediction_timestamp
  FROM FSI_DEMO.RAW_BANKING.CUSTOMER_FEATURES
")

message("Predictions written to FSI_DEMO.RAW_BANKING.CUSTOMER_CHURN_PREDICTIONS")

# ============================================================================
# 7. ANALYZE RESULTS
# ============================================================================

message("Analyzing prediction results...")

# Pull summary statistics
risk_summary <- dbGetQuery(conn, "
  SELECT 
    risk_category,
    COUNT(*) as customer_count,
    ROUND(AVG(churn_probability), 3) as avg_churn_prob,
    ROUND(AVG(total_balance), 2) as avg_balance,
    ROUND(AVG(total_accounts), 1) as avg_accounts
  FROM FSI_DEMO.RAW_BANKING.CUSTOMER_CHURN_PREDICTIONS
  GROUP BY risk_category
  ORDER BY avg_churn_prob DESC
")

message("\nChurn Risk Summary:")
print(risk_summary)

# High risk customers
high_risk <- dbGetQuery(conn, "
  SELECT 
    CIF_NUMBER,
    CUSTOMER_NAME,
    EMAIL,
    ROUND(churn_probability, 3) as churn_probability,
    ROUND(total_balance, 2) as total_balance,
    total_accounts,
    account_tenure_days
  FROM FSI_DEMO.RAW_BANKING.CUSTOMER_CHURN_PREDICTIONS
  WHERE risk_category = 'High Risk'
  ORDER BY churn_probability DESC
  LIMIT 10
")

message("\nTop 10 High Risk Customers:")
print(high_risk)

# ============================================================================
# 8. SUMMARY
# ============================================================================

cat("\n", paste(rep("=", 70), collapse = ""), "\n")
cat("ORBITAL DEPLOYMENT COMPLETE!\n")
cat(paste(rep("=", 70), collapse = ""), "\n\n")
cat("✓ Model trained on live Snowflake data\n")
cat("✓ Deployed as UDF: RAW_BANKING.PREDICT_CUSTOMER_CHURN()\n")
cat("✓ Predictions written to: FSI_DEMO.RAW_BANKING.CUSTOMER_CHURN_PREDICTIONS\n\n")
cat("You can now use the UDF in any SQL query:\n")
cat("  SELECT CIF_NUMBER, PREDICT_CUSTOMER_CHURN(...) FROM customers\n\n")
cat("Or query the predictions table:\n")
cat("  SELECT * FROM FSI_DEMO.RAW_BANKING.CUSTOMER_CHURN_PREDICTIONS\n")
cat(paste(rep("=", 70), collapse = ""), "\n")
