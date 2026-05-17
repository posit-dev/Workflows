# FSI Demo - Data Preparation Script
# This script pulls data from Snowflake and saves it locally for offline use

library(DBI)
library(dplyr)
library(readr)

# Connect to Snowflake (assumes connection already established)
# conn <- DBI::dbConnect(odbc::snowflake())

# Set warehouse and database
dbExecute(conn, "USE WAREHOUSE DEFAULT_WH")
dbExecute(conn, "USE DATABASE FSI_DEMO")

# Pull all raw banking data
message("Pulling branch data...")
branches <- dbGetQuery(conn, "SELECT * FROM FSI_DEMO.RAW_BANKING.BRANCH_MASTER")

message("Pulling customer data...")
customers <- dbGetQuery(conn, "SELECT * FROM FSI_DEMO.RAW_BANKING.CIF_CUSTOMER_MASTER")

message("Pulling account data...")
accounts <- dbGetQuery(conn, "SELECT * FROM FSI_DEMO.RAW_BANKING.CBS_ACCOUNT_MASTER")

message("Pulling customer address data...")
addresses <- dbGetQuery(conn, "SELECT * FROM FSI_DEMO.RAW_BANKING.CIF_CUSTOMER_ADDRESS")

message("Pulling transaction data...")
transactions <- dbGetQuery(conn, "SELECT * FROM FSI_DEMO.RAW_BANKING.TRANSACTION_STAGING")

# Save data locally
message("Saving data to local files...")
write_rds(branches, "fsi_demo/data/branches.rds")
write_rds(customers, "fsi_demo/data/customers.rds")
write_rds(accounts, "fsi_demo/data/accounts.rds")
write_rds(addresses, "fsi_demo/data/addresses.rds")
write_rds(transactions, "fsi_demo/data/transactions.rds")

# Also save as CSV for broader compatibility
write_csv(branches, "fsi_demo/data/branches.csv")
write_csv(customers, "fsi_demo/data/customers.csv")
write_csv(accounts, "fsi_demo/data/accounts.csv")
write_csv(addresses, "fsi_demo/data/addresses.csv")
write_csv(transactions, "fsi_demo/data/transactions.csv")

# Create a combined dataset for analysis
message("Creating combined analytical dataset...")
customer_analytics <- customers |>
  left_join(addresses |> filter(IS_PRIMARY_ADDRESS), by = "CIF_NUMBER") |>
  left_join(
    accounts |> 
      group_by(CIF_NUMBER) |> 
      summarise(
        total_accounts = n(),
        total_balance = sum(CURRENT_BALANCE, na.rm = TRUE),
        avg_balance = mean(CURRENT_BALANCE, na.rm = TRUE),
        total_credit_limit = sum(CREDIT_LIMIT, na.rm = TRUE),
        .groups = "drop"
      ),
    by = "CIF_NUMBER"
  )

write_rds(customer_analytics, "fsi_demo/data/customer_analytics.rds")
write_csv(customer_analytics, "fsi_demo/data/customer_analytics.csv")

message("Data preparation complete!")
message(sprintf("- %d branches", nrow(branches)))
message(sprintf("- %d customers", nrow(customers)))
message(sprintf("- %d accounts", nrow(accounts)))
message(sprintf("- %d addresses", nrow(addresses)))
message(sprintf("- %d transactions", nrow(transactions)))
