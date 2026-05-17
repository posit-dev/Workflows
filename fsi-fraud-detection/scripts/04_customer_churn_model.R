# Customer Segmentation Model
# K-means and Hierarchical Clustering for Customer 360 Analysis

library(DBI)
library(odbc)
library(tidyverse)
library(tidymodels)
library(factoextra)
library(cluster)
library(patchwork)
library(gt)
library(corrplot)

# Set seed for reproducibility
set.seed(42)

cat("================================================================================\n")
cat("CUSTOMER SEGMENTATION MODEL - K-MEANS & HIERARCHICAL CLUSTERING\n")
cat("================================================================================\n")
cat("Model Version: v1.0.0_R\n")
cat("Analysis Date:", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n\n")

# ============================================================================
# 1. CONNECT TO SNOWFLAKE AND LOAD DATA
# ============================================================================

cat("Connecting to Snowflake...\n")
con <- dbConnect(
  odbc::snowflake(),
  warehouse = "DEFAULT_WH",
  database = "FSI_DEMO",
  schema = "CORE_BANKING"
)
cat("✓ Connected to Snowflake\n\n")

cat("Loading customer 360 dataset...\n")

df <- dbGetQuery(con, "
SELECT 
    c.CUSTOMER_KEY,
    c.CIF_NUMBER,
    c.CUSTOMER_SEGMENT,
    c.CREDIT_SCORE,
    c.CUSTOMER_TENURE_YEARS,
    c.RISK_RATING,
    c.RELATIONSHIP_STATUS,
    c.AGE_BAND,
    c.CUSTOMER_TYPE,

    -- Revenue profile (monthly averages)
    r.TOTAL_MONTHS,
    r.AVG_MONTHLY_REVENUE,
    r.AVG_NET_INTEREST_INCOME,
    r.AVG_FEE_REVENUE,
    r.TOTAL_REVENUE,

    -- Digital engagement
    e.AVG_DAILY_LOGINS,
    e.AVG_ENGAGEMENT_SCORE,
    e.AVG_SESSION_MINUTES,
    e.MOBILE_PCT,
    e.WEB_PCT,
    e.TOTAL_ENGAGEMENT_DAYS,

    -- Account / balance profile
    a.NUM_ACCOUNTS,
    a.NUM_ACCOUNT_TYPES,
    a.HAS_DDA,
    a.HAS_CREDIT_CARD,
    a.HAS_LOAN,

    -- Balance behavior
    b.AVG_CURRENT_BALANCE,
    b.AVG_UTILIZATION_RATE,
    b.BALANCE_VOLATILITY,
    b.MAX_BALANCE,
    b.DORMANT_SNAPSHOT_PCT,

    -- Payment behavior
    p.TOTAL_PAYMENTS,
    p.AVG_DAYS_LATE,
    p.LATE_PAYMENT_RATE,
    p.MAX_DAYS_LATE

FROM FSI_DEMO.CORE_BANKING.DIM_CUSTOMER c

LEFT JOIN (
    SELECT CUSTOMER_KEY,
           COUNT(DISTINCT REVENUE_MONTH) AS TOTAL_MONTHS,
           AVG(TOTAL_REVENUE) AS AVG_MONTHLY_REVENUE,
           AVG(NET_INTEREST_INCOME) AS AVG_NET_INTEREST_INCOME,
           AVG(FEE_REVENUE) AS AVG_FEE_REVENUE,
           SUM(TOTAL_REVENUE) AS TOTAL_REVENUE
    FROM FSI_DEMO.ANALYTICS_BANKING.FACT_CUSTOMER_REVENUE
    GROUP BY CUSTOMER_KEY
) r ON c.CUSTOMER_KEY = r.CUSTOMER_KEY

LEFT JOIN (
    SELECT CUSTOMER_KEY,
           AVG(TOTAL_LOGIN_COUNT) AS AVG_DAILY_LOGINS,
           AVG(DIGITAL_ENGAGEMENT_SCORE) AS AVG_ENGAGEMENT_SCORE,
           AVG(SESSION_DURATION_MINUTES) AS AVG_SESSION_MINUTES,
           SUM(MOBILE_LOGIN_COUNT) * 1.0 / NULLIF(SUM(TOTAL_LOGIN_COUNT), 0) AS MOBILE_PCT,
           SUM(WEB_LOGIN_COUNT) * 1.0 / NULLIF(SUM(TOTAL_LOGIN_COUNT), 0) AS WEB_PCT,
           COUNT(DISTINCT ACTIVITY_DATE) AS TOTAL_ENGAGEMENT_DAYS
    FROM FSI_DEMO.ANALYTICS_BANKING.FACT_DIGITAL_ENGAGEMENT
    GROUP BY CUSTOMER_KEY
) e ON c.CUSTOMER_KEY = e.CUSTOMER_KEY

LEFT JOIN (
    SELECT CUSTOMER_KEY,
           COUNT(*) AS NUM_ACCOUNTS,
           COUNT(DISTINCT ACCOUNT_TYPE) AS NUM_ACCOUNT_TYPES,
           MAX(CASE WHEN ACCOUNT_TYPE = 'DDA' THEN 1 ELSE 0 END) AS HAS_DDA,
           MAX(CASE WHEN ACCOUNT_TYPE = 'CRD' THEN 1 ELSE 0 END) AS HAS_CREDIT_CARD,
           MAX(CASE WHEN ACCOUNT_TYPE = 'LOAN' THEN 1 ELSE 0 END) AS HAS_LOAN
    FROM FSI_DEMO.CORE_BANKING.DIM_ACCOUNT
    WHERE IS_CURRENT = 1
    GROUP BY CUSTOMER_KEY
) a ON c.CUSTOMER_KEY = a.CUSTOMER_KEY

LEFT JOIN (
    SELECT CUSTOMER_KEY,
           AVG(CURRENT_BALANCE) AS AVG_CURRENT_BALANCE,
           AVG(UTILIZATION_RATE) AS AVG_UTILIZATION_RATE,
           STDDEV(CURRENT_BALANCE) AS BALANCE_VOLATILITY,
           MAX(CURRENT_BALANCE) AS MAX_BALANCE,
           SUM(CASE WHEN IS_DORMANT THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS DORMANT_SNAPSHOT_PCT
    FROM FSI_DEMO.ANALYTICS_BANKING.FACT_ACCOUNT_BALANCE_DAILY
    GROUP BY CUSTOMER_KEY
) b ON c.CUSTOMER_KEY = b.CUSTOMER_KEY

LEFT JOIN (
    SELECT ph.CIF_NUMBER,
           COUNT(*) AS TOTAL_PAYMENTS,
           AVG(ph.DAYS_LATE) AS AVG_DAYS_LATE,
           SUM(CASE WHEN ph.DAYS_LATE > 30 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS LATE_PAYMENT_RATE,
           MAX(ph.DAYS_LATE) AS MAX_DAYS_LATE
    FROM FSI_DEMO.RAW_BANKING.PAYMENT_HISTORY ph
    GROUP BY ph.CIF_NUMBER
) p ON c.CIF_NUMBER = p.CIF_NUMBER

WHERE c.IS_CURRENT = 1
")

cat("✓ Loaded", nrow(df), "customers\n\n")

# ============================================================================
# 2. FEATURE PREPARATION
# ============================================================================

cat("Preparing clustering features...\n")

# Select clustering features
clustering_features <- c(
  "CREDIT_SCORE", "CUSTOMER_TENURE_YEARS",
  "AVG_MONTHLY_REVENUE", "TOTAL_REVENUE", "AVG_FEE_REVENUE",
  "AVG_DAILY_LOGINS", "AVG_ENGAGEMENT_SCORE", "AVG_SESSION_MINUTES", "MOBILE_PCT",
  "NUM_ACCOUNTS", "NUM_ACCOUNT_TYPES", "HAS_DDA", "HAS_CREDIT_CARD", "HAS_LOAN",
  "AVG_CURRENT_BALANCE", "AVG_UTILIZATION_RATE", "BALANCE_VOLATILITY",
  "AVG_DAYS_LATE", "LATE_PAYMENT_RATE"
)

# Prepare data for clustering
cluster_data <- df |>
  select(all_of(clustering_features)) |>
  mutate(across(everything(), ~replace_na(., 0)))

# Remove zero-variance features
zero_var_cols <- sapply(cluster_data, function(x) var(x, na.rm = TRUE) == 0 | is.na(var(x, na.rm = TRUE)))
if (any(zero_var_cols)) {
  cat("Removing", sum(zero_var_cols), "zero-variance features:\n")
  cat("  ", names(cluster_data)[zero_var_cols], "\n")
  cluster_data <- cluster_data[, !zero_var_cols]
}

# Scale the data
scaled_data <- scale(cluster_data)

# Remove any remaining NA/NaN/Inf values
if (any(!is.finite(scaled_data))) {
  cat("Warning: Removing non-finite values from scaled data\n")
  scaled_data[!is.finite(scaled_data)] <- 0
}

cat("✓ Prepared", ncol(scaled_data), "features for clustering\n")
cat("✓ Scaled data (mean=0, sd=1)\n\n")

# ============================================================================
# 3. EXPLORATORY ANALYSIS
# ============================================================================

cat("Generating exploratory visualizations...\n")

# Create output directory
dir.create("models/artifacts/segmentation_plots", showWarnings = FALSE, recursive = TRUE)

# Correlation heatmap
png("models/artifacts/segmentation_plots/correlation_heatmap.png", 
    width = 1200, height = 1000, res = 120)
corrplot(cor(cluster_data), 
         method = "color",
         type = "upper",
         tl.cex = 0.7,
         tl.col = "black",
         title = "Feature Correlation Matrix",
         mar = c(0, 0, 2, 0))
dev.off()

cat("✓ Correlation heatmap saved\n")

# Distribution plots for key features
key_features <- c("CREDIT_SCORE", "AVG_MONTHLY_REVENUE", "AVG_ENGAGEMENT_SCORE", 
                  "AVG_CURRENT_BALANCE", "CUSTOMER_TENURE_YEARS", "AVG_UTILIZATION_RATE")

dist_plot <- cluster_data |>
  select(all_of(key_features)) |>
  pivot_longer(everything(), names_to = "feature", values_to = "value") |>
  ggplot(aes(x = value)) +
  geom_histogram(bins = 30, fill = "steelblue", alpha = 0.7) +
  facet_wrap(~feature, scales = "free", ncol = 3) +
  labs(title = "Distribution of Key Features") +
  theme_minimal()

ggsave("models/artifacts/segmentation_plots/feature_distributions.png", 
       dist_plot, width = 12, height = 8)

cat("✓ Feature distributions saved\n\n")

# ============================================================================
# 4. OPTIMAL K SELECTION
# ============================================================================

cat("Determining optimal number of clusters...\n")
cat("This may take a few minutes...\n\n")

# Elbow method
elbow_plot <- fviz_nbclust(scaled_data, kmeans, method = "wss", k.max = 10) +
  labs(title = "Elbow Method") +
  theme_minimal()

# Silhouette method
silhouette_plot <- fviz_nbclust(scaled_data, kmeans, method = "silhouette", k.max = 10) +
  labs(title = "Silhouette Method") +
  theme_minimal()

# Gap statistic
gap_plot <- fviz_nbclust(scaled_data, kmeans, method = "gap_stat", k.max = 10) +
  labs(title = "Gap Statistic Method") +
  theme_minimal()

# Combine plots
optimal_k_plot <- elbow_plot + silhouette_plot + gap_plot +
  plot_annotation(title = "Optimal Number of Clusters - Three Methods")

ggsave("models/artifacts/segmentation_plots/optimal_k_selection.png", 
       optimal_k_plot, width = 15, height = 5)

cat("✓ Optimal K selection plots saved\n")
cat("  Review plots to determine optimal K (typically 4-6)\n\n")

# ============================================================================
# 5. K-MEANS CLUSTERING
# ============================================================================

# Set optimal K (adjust based on plots)
optimal_k <- 5
cat("Running K-means clustering with K =", optimal_k, "...\n")

# Run K-means
set.seed(42)
km_result <- kmeans(scaled_data, centers = optimal_k, nstart = 25, iter.max = 100)

cat("✓ K-means clustering complete\n")
cat("  Total within-cluster sum of squares:", round(km_result$tot.withinss, 2), "\n")
cat("  Between-cluster sum of squares:", round(km_result$betweenss, 2), "\n")
cat("  Ratio (between/total):", round(km_result$betweenss / km_result$totss, 3), "\n\n")

# Add cluster assignments to original data
df$CLUSTER_ID <- km_result$cluster

# Cluster sizes
cat("Cluster Sizes:\n")
print(table(df$CLUSTER_ID))
cat("\n")

# ============================================================================
# 6. HIERARCHICAL CLUSTERING (FOR COMPARISON)
# ============================================================================

cat("Running hierarchical clustering for comparison...\n")

# Compute distance matrix (sample for large datasets)
set.seed(42)
sample_size <- min(1000, nrow(scaled_data))
sample_idx <- sample(nrow(scaled_data), sample_size)

dist_matrix <- dist(scaled_data[sample_idx, ], method = "euclidean")
hc_result <- hclust(dist_matrix, method = "ward.D2")

# Plot dendrogram
dend_plot <- fviz_dend(hc_result, k = optimal_k, 
                       cex = 0.5,
                       main = "Hierarchical Clustering Dendrogram",
                       xlab = "Customers (sample)",
                       ylab = "Height")

ggsave("models/artifacts/segmentation_plots/dendrogram.png", 
       dend_plot, width = 12, height = 8)

cat("✓ Hierarchical clustering complete\n")
cat("✓ Dendrogram saved\n\n")

# ============================================================================
# 7. CLUSTER PROFILING
# ============================================================================

cat("================================================================================\n")
cat("CLUSTER PROFILING\n")
cat("================================================================================\n\n")

# Calculate cluster profiles
cluster_profiles <- df |>
  group_by(CLUSTER_ID) |>
  summarise(
    Size = n(),
    Pct = round(n() / nrow(df) * 100, 1),
    Avg_Credit_Score = round(mean(CREDIT_SCORE, na.rm = TRUE), 0),
    Avg_Tenure_Years = round(mean(CUSTOMER_TENURE_YEARS, na.rm = TRUE), 1),
    Avg_Monthly_Revenue = round(mean(AVG_MONTHLY_REVENUE, na.rm = TRUE), 0),
    Total_Revenue = round(mean(TOTAL_REVENUE, na.rm = TRUE), 0),
    Avg_Engagement_Score = round(mean(AVG_ENGAGEMENT_SCORE, na.rm = TRUE), 1),
    Avg_Daily_Logins = round(mean(AVG_DAILY_LOGINS, na.rm = TRUE), 2),
    Mobile_Pct = round(mean(MOBILE_PCT, na.rm = TRUE) * 100, 1),
    Avg_Balance = round(mean(AVG_CURRENT_BALANCE, na.rm = TRUE), 0),
    Avg_Utilization = round(mean(AVG_UTILIZATION_RATE, na.rm = TRUE) * 100, 1),
    Late_Payment_Rate = round(mean(LATE_PAYMENT_RATE, na.rm = TRUE) * 100, 1),
    Num_Accounts = round(mean(NUM_ACCOUNTS, na.rm = TRUE), 1)
  ) |>
  arrange(CLUSTER_ID)

# Display profile table
cat("Cluster Profiles:\n")
print(cluster_profiles)
cat("\n")

# Assign descriptive segment names based on profiles
segment_names <- c(
  "1" = "Mass Market Stable",
  "2" = "High-Value Digital",
  "3" = "At-Risk Low-Engagement",
  "4" = "Affluent Traditional",
  "5" = "New Growth"
)

# Adjust names based on actual cluster characteristics
# (You may need to review cluster_profiles and adjust these manually)

# Map cluster IDs to segment names
df$SEGMENT_NAME <- segment_names[as.character(df$CLUSTER_ID)]

# Create formatted profile table with gt
profile_table <- cluster_profiles |>
  gt() |>
  tab_header(
    title = "Customer Segment Profiles",
    subtitle = "K-means Clustering Results"
  ) |>
  fmt_number(
    columns = c(Avg_Monthly_Revenue, Total_Revenue, Avg_Balance),
    decimals = 0
  ) |>
  fmt_percent(
    columns = c(Pct, Mobile_Pct, Avg_Utilization, Late_Payment_Rate),
    decimals = 1,
    scale_values = FALSE
  ) |>
  cols_label(
    CLUSTER_ID = "Cluster",
    Size = "Size",
    Pct = "% of Total",
    Avg_Credit_Score = "Credit Score",
    Avg_Tenure_Years = "Tenure (Yrs)",
    Avg_Monthly_Revenue = "Monthly Revenue",
    Total_Revenue = "Total Revenue",
    Avg_Engagement_Score = "Engagement",
    Avg_Daily_Logins = "Daily Logins",
    Mobile_Pct = "Mobile %",
    Avg_Balance = "Avg Balance",
    Avg_Utilization = "Utilization %",
    Late_Payment_Rate = "Late Payment %",
    Num_Accounts = "# Accounts"
  )

# Save profile table as HTML
gtsave(profile_table, "models/artifacts/segmentation_plots/cluster_profiles.html")
cat("✓ Cluster profile table saved\n\n")

# ============================================================================
# 8. VISUALIZATIONS
# ============================================================================

cat("Generating cluster visualizations...\n")

# PCA biplot with clusters
pca_plot <- fviz_cluster(km_result, 
                         data = scaled_data,
                         ellipse.type = "convex",
                         palette = "jco",
                         ggtheme = theme_minimal(),
                         main = "Customer Segments - PCA Biplot")

ggsave("models/artifacts/segmentation_plots/pca_cluster_plot.png", 
       pca_plot, width = 10, height = 8)

cat("✓ PCA cluster plot saved\n")

# Cluster size bar chart
size_plot <- cluster_profiles |>
  ggplot(aes(x = factor(CLUSTER_ID), y = Size, fill = factor(CLUSTER_ID))) +
  geom_col() +
  geom_text(aes(label = paste0(Size, "\n(", Pct, "%)")), 
            vjust = -0.5, size = 3.5) +
  scale_fill_brewer(palette = "Set2") +
  labs(title = "Cluster Size Distribution",
       x = "Cluster ID",
       y = "Number of Customers") +
  theme_minimal() +
  theme(legend.position = "none")

ggsave("models/artifacts/segmentation_plots/cluster_sizes.png", 
       size_plot, width = 10, height = 6)

cat("✓ Cluster size plot saved\n")

# Box plots of key features by cluster
key_features_long <- df |>
  select(CLUSTER_ID, all_of(key_features)) |>
  pivot_longer(-CLUSTER_ID, names_to = "Feature", values_to = "Value")

boxplot_features <- key_features_long |>
  ggplot(aes(x = factor(CLUSTER_ID), y = Value, fill = factor(CLUSTER_ID))) +
  geom_boxplot() +
  facet_wrap(~Feature, scales = "free_y", ncol = 3) +
  scale_fill_brewer(palette = "Set2") +
  labs(title = "Feature Distribution by Cluster",
       x = "Cluster ID",
       y = "Value") +
  theme_minimal() +
  theme(legend.position = "none")

ggsave("models/artifacts/segmentation_plots/feature_boxplots.png", 
       boxplot_features, width = 14, height = 10)

cat("✓ Feature boxplots saved\n")

# Radar chart of cluster means (normalized)
cluster_means <- df |>
  group_by(CLUSTER_ID) |>
  summarise(
    Credit_Score = mean(CREDIT_SCORE, na.rm = TRUE) / 850,
    Tenure = mean(CUSTOMER_TENURE_YEARS, na.rm = TRUE) / max(df$CUSTOMER_TENURE_YEARS, na.rm = TRUE),
    Revenue = mean(AVG_MONTHLY_REVENUE, na.rm = TRUE) / max(df$AVG_MONTHLY_REVENUE, na.rm = TRUE),
    Engagement = mean(AVG_ENGAGEMENT_SCORE, na.rm = TRUE) / 100,
    Balance = mean(AVG_CURRENT_BALANCE, na.rm = TRUE) / max(df$AVG_CURRENT_BALANCE, na.rm = TRUE),
    Accounts = mean(NUM_ACCOUNTS, na.rm = TRUE) / max(df$NUM_ACCOUNTS, na.rm = TRUE)
  )

radar_plot <- cluster_means |>
  pivot_longer(-CLUSTER_ID, names_to = "Metric", values_to = "Value") |>
  ggplot(aes(x = Metric, y = Value, group = CLUSTER_ID, color = factor(CLUSTER_ID))) +
  geom_polygon(aes(fill = factor(CLUSTER_ID)), alpha = 0.2) +
  geom_point(size = 3) +
  geom_line(size = 1) +
  coord_polar() +
  scale_y_continuous(limits = c(0, 1)) +
  scale_color_brewer(palette = "Set2") +
  scale_fill_brewer(palette = "Set2") +
  labs(title = "Cluster Profiles - Radar Chart (Normalized)",
       color = "Cluster",
       fill = "Cluster") +
  theme_minimal() +
  theme(axis.text.x = element_text(size = 10))

ggsave("models/artifacts/segmentation_plots/radar_chart.png", 
       radar_plot, width = 10, height = 8)

cat("✓ Radar chart saved\n\n")

# ============================================================================
# 9. SILHOUETTE ANALYSIS
# ============================================================================

cat("Computing silhouette scores...\n")

# Calculate silhouette scores
sil_scores <- silhouette(km_result$cluster, dist(scaled_data))
sil_plot <- fviz_silhouette(sil_scores, palette = "jco", ggtheme = theme_minimal()) +
  labs(title = "Silhouette Plot - Cluster Quality")

ggsave("models/artifacts/segmentation_plots/silhouette_plot.png", 
       sil_plot, width = 10, height = 8)

avg_sil <- mean(sil_scores[, "sil_width"])
cat("✓ Average silhouette width:", round(avg_sil, 3), "\n")
cat("  (Values > 0.5 indicate good clustering)\n\n")

# ============================================================================
# 10. SAVE MODEL AND RESULTS
# ============================================================================

cat("Saving model artifacts...\n")

# Save K-means model
saveRDS(km_result, "models/artifacts/customer_segmentation_model.rds")
cat("✓ K-means model saved\n")

# Save hierarchical clustering result
saveRDS(hc_result, "models/artifacts/hierarchical_clustering_model.rds")
cat("✓ Hierarchical clustering model saved\n")

# Save cluster profiles
saveRDS(cluster_profiles, "models/artifacts/cluster_profiles.rds")
cat("✓ Cluster profiles saved\n\n")

# ============================================================================
# 11. WRITE SEGMENTS TO SNOWFLAKE
# ============================================================================

cat("================================================================================\n")
cat("WRITING SEGMENTS TO SNOWFLAKE\n")
cat("================================================================================\n\n")

# Prepare segment data for Snowflake
segment_df <- data.frame(
  CUSTOMER_KEY = df$CUSTOMER_KEY,
  CIF_NUMBER = df$CIF_NUMBER,
  CLUSTER_ID = as.integer(df$CLUSTER_ID),
  SEGMENT_NAME = df$SEGMENT_NAME,
  MODEL_VERSION = "v1.0.0_R",
  SCORED_AT = Sys.time()
)

cat("Writing", nrow(segment_df), "customer segments to Snowflake...\n")

# Write to Snowflake
dbWriteTable(
  con, 
  Id(database = "FSI_DEMO", schema = "ANALYTICS_BANKING", table = "ML_CUSTOMER_SEGMENTS"),
  segment_df, 
  overwrite = TRUE
)

cat("✓ Segments written to FSI_DEMO.ANALYTICS_BANKING.ML_CUSTOMER_SEGMENTS\n\n")

# Display segment distribution
cat("Segment Distribution:\n")
segment_summary <- segment_df |>
  group_by(SEGMENT_NAME) |>
  summarise(Count = n(), Pct = round(n() / nrow(segment_df) * 100, 1)) |>
  arrange(desc(Count))

print(segment_summary)
cat("\n")

# ============================================================================
# 12. SUMMARY
# ============================================================================

cat("================================================================================\n")
cat("SEGMENTATION COMPLETE\n")
cat("================================================================================\n")
cat("Model Version: v1.0.0_R\n")
cat("Number of Clusters:", optimal_k, "\n")
cat("Total Customers:", nrow(df), "\n")
cat("Average Silhouette Width:", round(avg_sil, 3), "\n")
cat("Between/Total SS Ratio:", round(km_result$betweenss / km_result$totss, 3), "\n")
cat("\nModel saved to: models/artifacts/customer_segmentation_model.rds\n")
cat("Segments written to: FSI_DEMO.ANALYTICS_BANKING.ML_CUSTOMER_SEGMENTS\n")
cat("Plots saved to: models/artifacts/segmentation_plots/\n")
cat("================================================================================\n\n")

# Close Snowflake connection
dbDisconnect(con)
cat("✓ Snowflake connection closed\n")