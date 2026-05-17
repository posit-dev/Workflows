# Credit Risk / Loan Default Prediction Model
# Using tidymodels + XGBoost with hyperparameter tuning

library(DBI)
library(odbc)
library(tidymodels)
library(xgboost)
library(vip)
library(probably)
library(ggplot2)
library(SHAPforxgboost)
library(dplyr)
library(purrr)

# Set seed for reproducibility
set.seed(42)

cat("================================================================================\n")
cat("CREDIT RISK MODEL TRAINING - TIDYMODELS + XGBOOST\n")
cat("================================================================================\n")
cat("Model Version: v1.0.0_R\n")
cat("Training Date:", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n\n")

# ============================================================================
# 1. CONNECT TO SNOWFLAKE
# ============================================================================

cat("Connecting to Snowflake...\n")
con <- dbConnect(
  odbc::snowflake(),
  warehouse = "DEFAULT_WH",
  database = "FSI_DEMO",
  schema = "RAW_BANKING"
)
cat("✓ Connected to Snowflake\n\n")

# ============================================================================
# 2. LOAD DATA
# ============================================================================

cat("Loading approved loan applications with default labels...\n")

df <- dbGetQuery(con, "
SELECT 
    la.APPLICATION_ID,
    la.CIF_NUMBER,
    la.LOAN_TYPE,
    la.LOAN_PURPOSE,
    la.REQUESTED_AMOUNT,
    la.REQUESTED_TERM_MONTHS,
    la.COLLATERAL_TYPE,
    la.COLLATERAL_VALUE,
    la.APPLICANT_ANNUAL_INCOME,
    la.CO_APPLICANT_INCOME,
    la.DEBT_TO_INCOME_RATIO,
    la.CREDIT_SCORE_AT_APPLICATION,
    la.EMPLOYMENT_STATUS,
    la.YEARS_AT_EMPLOYER,
    la.APPLICATION_CHANNEL,
    la.APPROVED_AMOUNT,
    la.APPROVED_INTEREST_RATE,
    la.IS_DEFAULT,
    c.CUSTOMER_TENURE_YEARS,
    c.RISK_RATING,
    c.CUSTOMER_SEGMENT,
    c.AGE_BAND,
    ph.AVG_DAYS_LATE,
    ph.MAX_DAYS_LATE,
    ph.LATE_PAYMENT_COUNT,
    ph.TOTAL_PAYMENTS
FROM FSI_DEMO.RAW_BANKING.LOAN_APPLICATION la
LEFT JOIN FSI_DEMO.CORE_BANKING.DIM_CUSTOMER c 
    ON la.CIF_NUMBER = c.CIF_NUMBER AND c.IS_CURRENT = 1
LEFT JOIN (
    SELECT CIF_NUMBER,
           AVG(DAYS_LATE) AS AVG_DAYS_LATE,
           MAX(DAYS_LATE) AS MAX_DAYS_LATE,
           SUM(CASE WHEN DAYS_LATE > 30 THEN 1 ELSE 0 END) AS LATE_PAYMENT_COUNT,
           COUNT(*) AS TOTAL_PAYMENTS
    FROM FSI_DEMO.RAW_BANKING.PAYMENT_HISTORY
    GROUP BY CIF_NUMBER
) ph ON la.CIF_NUMBER = ph.CIF_NUMBER
WHERE la.DECISION_STATUS = 'APPROVED'
")

cat("✓ Loaded", nrow(df), "approved loans\n")
cat("  Default rate:", sprintf("%.2f%%", mean(df$IS_DEFAULT, na.rm = TRUE) * 100), "\n")
cat("  Defaults:", sum(df$IS_DEFAULT, na.rm = TRUE), "\n")
cat("  Non-defaults:", sum(!df$IS_DEFAULT, na.rm = TRUE), "\n\n")

# Convert target to factor
df <- df |>
  mutate(
    IS_DEFAULT = factor(
      ifelse(IS_DEFAULT, "default", "no_default"),
      levels = c("default", "no_default")
    )
  )

# ============================================================================
# 3. TRAIN/TEST SPLIT
# ============================================================================

cat("Splitting data (75/25, stratified)...\n")
data_split <- initial_split(df, prop = 0.75, strata = IS_DEFAULT)
train_data <- training(data_split)
test_data <- testing(data_split)

cat("✓ Training set:", nrow(train_data), "samples\n")
cat("  Default rate:", sprintf("%.2f%%", mean(train_data$IS_DEFAULT == "default") * 100), "\n")
cat("✓ Test set:", nrow(test_data), "samples\n")
cat("  Default rate:", sprintf("%.2f%%", mean(test_data$IS_DEFAULT == "default") * 100), "\n\n")

# ============================================================================
# 4. FEATURE ENGINEERING RECIPE
# ============================================================================

cat("Creating feature engineering recipe...\n")

credit_recipe <- recipe(IS_DEFAULT ~ ., data = train_data) |>
  # Remove ID columns
  step_rm(APPLICATION_ID, CIF_NUMBER, LOAN_PURPOSE, CUSTOMER_SEGMENT) |>
  
  # Derived features
  step_mutate(
    LOAN_TO_INCOME_RATIO = REQUESTED_AMOUNT / APPLICANT_ANNUAL_INCOME,
    HAS_COLLATERAL = ifelse(COLLATERAL_TYPE != "NONE", 1, 0),
    HAS_COAPPLICANT = ifelse(!is.na(CO_APPLICANT_INCOME), 1, 0),
    PAYMENT_DELINQUENCY_RATE = ifelse(TOTAL_PAYMENTS > 0, 
                                      LATE_PAYMENT_COUNT / TOTAL_PAYMENTS, 
                                      0)
  ) |>
  
  # Impute missing values
  step_impute_median(all_numeric_predictors()) |>
  
  # Create dummy variables for categorical features
  step_dummy(LOAN_TYPE, EMPLOYMENT_STATUS, COLLATERAL_TYPE, 
             APPLICATION_CHANNEL, RISK_RATING, AGE_BAND) |>
  
  # Normalize numeric predictors
  step_normalize(all_numeric_predictors()) |>
  
  # Remove zero-variance features
  step_zv(all_predictors())

cat("✓ Recipe created with feature engineering steps\n\n")

# ============================================================================
# 5. MODEL SPECIFICATION
# ============================================================================

cat("Defining XGBoost model specification...\n")

# Calculate scale_pos_weight for class imbalance
scale_pos_weight <- sum(train_data$IS_DEFAULT == "no_default") / 
                    sum(train_data$IS_DEFAULT == "default")

cat("  Class imbalance handling: scale_pos_weight =", round(scale_pos_weight, 2), "\n")

xgb_spec <- boost_tree(
  trees = tune(),
  tree_depth = tune(),
  learn_rate = tune(),
  min_n = tune(),
  sample_size = tune()
) |>
  set_engine("xgboost", scale_pos_weight = scale_pos_weight) |>
  set_mode("classification")

cat("✓ Model specification created\n\n")

# ============================================================================
# 6. CREATE WORKFLOW
# ============================================================================

cat("Creating workflow...\n")

credit_wf <- workflow() |>
  add_recipe(credit_recipe) |>
  add_model(xgb_spec)

cat("✓ Workflow created\n\n")

# ============================================================================
# 7. HYPERPARAMETER TUNING
# ============================================================================

cat("Setting up hyperparameter tuning...\n")

# Create cross-validation folds
cv_folds <- vfold_cv(train_data, v = 5, strata = IS_DEFAULT)
cat("✓ Created 5-fold cross-validation\n")

# Create tuning grid
xgb_grid <- grid_latin_hypercube(
  trees(range = c(100, 500)),
  tree_depth(range = c(3, 10)),
  learn_rate(range = c(-3, -0.5)),
  min_n(range = c(2, 20)),
  sample_size = sample_prop(range = c(0.5, 1.0)),
  size = 30
)

cat("✓ Created tuning grid with 30 parameter combinations\n\n")

cat("Starting hyperparameter tuning (this may take several minutes)...\n")
cat("Optimizing on ROC-AUC...\n\n")

# Tune the model
tune_results <- tune_grid(
  credit_wf,
  resamples = cv_folds,
  grid = xgb_grid,
  metrics = metric_set(roc_auc, accuracy, precision, recall),
  control = control_grid(save_pred = TRUE, verbose = TRUE)
)

cat("\n✓ Tuning complete\n\n")

# Show best results
cat("Top 5 models by ROC-AUC:\n")
show_best(tune_results, metric = "roc_auc", n = 5) |> print()

# Select best model
best_params <- select_best(tune_results, metric = "roc_auc")
cat("\nBest hyperparameters:\n")
print(best_params)

# ============================================================================
# 8. FINALIZE AND FIT MODEL
# ============================================================================

cat("\nFinalizing model with best hyperparameters...\n")

final_wf <- finalize_workflow(credit_wf, best_params)

cat("Training final model on full training set...\n")
final_fit <- fit(final_wf, data = train_data)

cat("✓ Final model trained\n\n")

# ============================================================================
# 9. EVALUATE ON TEST SET
# ============================================================================

cat("================================================================================\n")
cat("MODEL EVALUATION\n")
cat("================================================================================\n\n")

# Generate predictions
test_predictions <- augment(final_fit, test_data)

# Classification metrics
test_metrics <- test_predictions |>
  metrics(truth = IS_DEFAULT, estimate = .pred_class, .pred_default)

cat("Classification Metrics:\n")
print(test_metrics)
cat("\n")

# Additional metrics
conf_mat_obj <- conf_mat(test_predictions, truth = IS_DEFAULT, estimate = .pred_class)
cat("Confusion Matrix:\n")
print(conf_mat_obj)
cat("\n")

# ROC-AUC
roc_auc_value <- roc_auc(test_predictions, truth = IS_DEFAULT, .pred_default)$.estimate
cat("ROC-AUC Score:", round(roc_auc_value, 4), "\n\n")

# ============================================================================
# 10. VISUALIZATIONS
# ============================================================================

cat("Generating evaluation plots...\n")

# Create output directory
dir.create("models/artifacts/plots", showWarnings = FALSE, recursive = TRUE)

# ROC Curve
roc_plot <- test_predictions |>
  roc_curve(truth = IS_DEFAULT, .pred_default) |>
  autoplot() +
  labs(title = "ROC Curve - Credit Risk Model",
       subtitle = sprintf("AUC = %.4f", roc_auc_value)) +
  theme_minimal()

ggsave("models/artifacts/plots/roc_curve.png", roc_plot, width = 8, height = 6)
cat("✓ ROC curve saved\n")

# Confusion Matrix Heatmap
cm_plot <- autoplot(conf_mat_obj, type = "heatmap") +
  labs(title = "Confusion Matrix - Credit Risk Model") +
  theme_minimal()

ggsave("models/artifacts/plots/confusion_matrix.png", cm_plot, width = 8, height = 6)
cat("✓ Confusion matrix saved\n")

# Precision-Recall Curve
pr_plot <- test_predictions |>
  pr_curve(truth = IS_DEFAULT, .pred_default) |>
  autoplot() +
  labs(title = "Precision-Recall Curve") +
  theme_minimal()

ggsave("models/artifacts/plots/precision_recall.png", pr_plot, width = 8, height = 6)
cat("✓ Precision-recall curve saved\n")

# ============================================================================
# 11. FEATURE IMPORTANCE
# ============================================================================

cat("\nComputing feature importance...\n")

# Extract the fitted xgboost model
xgb_fit <- extract_fit_engine(final_fit)

# Variable importance plot
vip_plot <- vip(xgb_fit, num_features = 15) +
  labs(title = "Top 15 Features - Credit Risk Model") +
  theme_minimal()

ggsave("models/artifacts/plots/feature_importance.png", vip_plot, width = 10, height = 8)
cat("✓ Feature importance plot saved\n")

# Print top features
cat("\nTop 15 Most Important Features:\n")
vip_data <- vi(xgb_fit) |> 
  arrange(desc(Importance)) |>
  head(15)
print(vip_data)

# ============================================================================
# 12. SHAP VALUES
# ============================================================================

cat("\nComputing SHAP values...\n")

# Prepare data for SHAP
train_processed <- bake(prep(credit_recipe), new_data = train_data)
train_matrix <- train_processed |>
  select(-IS_DEFAULT) |>
  as.matrix()

# Compute SHAP values (sample for speed)
set.seed(42)
sample_idx <- sample(nrow(train_matrix), min(500, nrow(train_matrix)))
shap_values <- shap.values(xgb_fit, X_train = train_matrix[sample_idx, ])

# SHAP summary plot
png("models/artifacts/plots/shap_summary.png", width = 1000, height = 800)
shap.plot.summary.wrap1(xgb_fit, X = train_matrix[sample_idx, ], top_n = 15)
dev.off()

cat("✓ SHAP summary plot saved\n\n")

# ============================================================================
# 13. SAVE MODEL
# ============================================================================

cat("Saving model artifacts...\n")

# Save the final fitted workflow
saveRDS(final_fit, "models/artifacts/credit_risk_model_R.rds")
cat("✓ Model saved to: models/artifacts/credit_risk_model_R.rds\n")

# Save model metadata
model_metadata <- list(
  model_version = "v1.0.0_R",
  trained_at = Sys.time(),
  training_rows = nrow(train_data),
  test_rows = nrow(test_data),
  default_rate = mean(train_data$IS_DEFAULT == "default"),
  roc_auc = roc_auc_value,
  best_params = best_params,
  metrics = test_metrics
)

saveRDS(model_metadata, "models/artifacts/credit_risk_metadata.rds")
cat("✓ Model metadata saved\n\n")

# ============================================================================
# 14. SCORE ALL LOANS AND WRITE TO SNOWFLAKE
# ============================================================================

cat("================================================================================\n")
cat("SCORING ALL APPROVED LOANS\n")
cat("================================================================================\n\n")

cat("Scoring test set...\n")

# Generate predictions with risk tiers
scores_df <- test_predictions |>
  mutate(
    DEFAULT_PROBABILITY = .pred_default,
    DEFAULT_PREDICTION = as.integer(.pred_class == "default"),
    RISK_TIER = case_when(
      .pred_default < 0.1  ~ "LOW_RISK",
      .pred_default < 0.3  ~ "MODERATE_RISK",
      .pred_default < 0.5  ~ "HIGH_RISK",
      TRUE                 ~ "VERY_HIGH_RISK"
    ),
    MODEL_VERSION = "v1.0.0_R",
    SCORED_AT = Sys.time()
  ) |>
  select(APPLICATION_ID, CIF_NUMBER, DEFAULT_PROBABILITY, DEFAULT_PREDICTION, 
         RISK_TIER, MODEL_VERSION, SCORED_AT)

cat("✓ Scored", nrow(scores_df), "loans\n")
cat("  Predicted defaults:", sum(scores_df$DEFAULT_PREDICTION), "\n")
cat("\nRisk Tier Distribution:\n")
print(table(scores_df$RISK_TIER))
cat("\n")

# Write to Snowflake
cat("Writing predictions to FSI_DEMO.ANALYTICS_BANKING.ML_CREDIT_RISK_SCORES...\n")

dbWriteTable(
  con, 
  Id(database = "FSI_DEMO", schema = "ANALYTICS_BANKING", table = "ML_CREDIT_RISK_SCORES"),
  scores_df, 
  overwrite = TRUE
)

cat("✓ Predictions written to Snowflake\n\n")

# ============================================================================
# 15. SUMMARY
# ============================================================================

cat("================================================================================\n")
cat("TRAINING COMPLETE\n")
cat("================================================================================\n")
cat("Model Version: v1.0.0_R\n")
cat("Model Path: models/artifacts/credit_risk_model_R.rds\n")
cat("ROC-AUC:", round(roc_auc_value, 4), "\n")
cat("Predictions written to: FSI_DEMO.ANALYTICS_BANKING.ML_CREDIT_RISK_SCORES\n")
cat("Plots saved to: models/artifacts/plots/\n")
cat("================================================================================\n\n")

# Close connection
dbDisconnect(con)
cat("✓ Snowflake connection closed\n")