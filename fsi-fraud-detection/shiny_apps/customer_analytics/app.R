# FSI Demo - Customer Analytics Dashboard
# Interactive Shiny application for banking analytics

library(shiny)
library(bslib)
library(dplyr)
library(ggplot2)
library(readr)
library(DT)
library(plotly)

# Load data
customers <- read_rds("../data/customers.rds")
accounts <- read_rds("../data/accounts.rds")
transactions <- read_rds("../data/transactions.rds")
branches <- read_rds("../data/branches.rds")

# Load ML models
credit_model <- read_rds("../models/credit_risk_model.rds")
churn_model <- read_rds("../models/churn_model.rds")

# Prepare combined data
customer_summary <- customers |>
  left_join(
    accounts |> 
      group_by(CIF_NUMBER) |> 
      summarise(
        total_accounts = n(),
        total_balance = sum(CURRENT_BALANCE, na.rm = TRUE),
        avg_balance = mean(CURRENT_BALANCE, na.rm = TRUE),
        .groups = "drop"
      ),
    by = "CIF_NUMBER"
  ) |>
  mutate(
    age = as.numeric(difftime(Sys.Date(), DATE_OF_BIRTH, units = "days")) / 365.25
  )

# UI
ui <- page_sidebar(
  title = "AmeriFirst Banking Analytics",
  theme = bs_theme(bootswatch = "flatly"),
  
  sidebar = sidebar(
    width = 300,
    h4("Filters"),
    selectInput("customer_type", "Customer Type:",
                choices = c("All", unique(customers$CUSTOMER_TYPE)),
                selected = "All"),
    selectInput("risk_rating", "Risk Rating:",
                choices = c("All", unique(customers$RISK_RATING)),
                selected = "All"),
    selectInput("relationship_status", "Status:",
                choices = c("All", unique(customers$RELATIONSHIP_STATUS)),
                selected = "All"),
    hr(),
    h5("Summary Statistics"),
    verbatimTextOutput("summary_stats")
  ),
  
  navset_card_tab(
    nav_panel("Overview",
      layout_columns(
        value_box(
          title = "Total Customers",
          value = textOutput("total_customers"),
          showcase = icon("users"),
          theme = "primary"
        ),
        value_box(
          title = "Total Deposits",
          value = textOutput("total_deposits"),
          showcase = icon("dollar-sign"),
          theme = "success"
        ),
        value_box(
          title = "At-Risk Customers",
          value = textOutput("at_risk_customers"),
          showcase = icon("exclamation-triangle"),
          theme = "warning"
        )
      ),
      layout_columns(
        card(
          card_header("Customer Distribution by Risk Rating"),
          plotlyOutput("risk_distribution")
        ),
        card(
          card_header("Account Balance Distribution"),
          plotlyOutput("balance_distribution")
        )
      ),
      card(
        card_header("Customer Demographics"),
        plotlyOutput("age_distribution")
      )
    ),
    
    nav_panel("Transactions",
      card(
        card_header("Recent Transactions"),
        DTOutput("transactions_table")
      ),
      layout_columns(
        card(
          card_header("Transaction Volume by Channel"),
          plotlyOutput("channel_volume")
        ),
        card(
          card_header("Transaction Amount by Merchant"),
          plotlyOutput("merchant_amounts")
        )
      )
    ),
    
    nav_panel("ML Predictions",
      layout_columns(
        card(
          card_header("Credit Risk Predictions"),
          p("Distribution of predicted credit risk categories across customers"),
          plotlyOutput("credit_risk_plot")
        ),
        card(
          card_header("Churn Risk Analysis"),
          p("Customers predicted to be at risk of churning"),
          plotlyOutput("churn_risk_plot")
        )
      ),
      card(
        card_header("High-Risk Customers"),
        DTOutput("high_risk_table")
      )
    ),
    
    nav_panel("Branch Performance",
      card(
        card_header("Branch Metrics"),
        DTOutput("branch_table")
      ),
      card(
        card_header("Customers by Branch Region"),
        plotlyOutput("branch_region_plot")
      )
    )
  )
)

# Server
server <- function(input, output, session) {
  
  # Reactive filtered data
  filtered_customers <- reactive({
    data <- customer_summary
    
    if (input$customer_type != "All") {
      data <- data |> filter(CUSTOMER_TYPE == input$customer_type)
    }
    if (input$risk_rating != "All") {
      data <- data |> filter(RISK_RATING == input$risk_rating)
    }
    if (input$relationship_status != "All") {
      data <- data |> filter(RELATIONSHIP_STATUS == input$relationship_status)
    }
    
    data
  })
  
  # Summary statistics
  output$summary_stats <- renderText({
    data <- filtered_customers()
    paste0(
      "Customers: ", nrow(data), "\n",
      "Avg Balance: $", format(round(mean(data$total_balance, na.rm = TRUE)), big.mark = ","), "\n",
      "Avg Age: ", round(mean(data$age, na.rm = TRUE), 1), " years"
    )
  })
  
  # Value boxes
  output$total_customers <- renderText({
    format(nrow(filtered_customers()), big.mark = ",")
  })
  
  output$total_deposits <- renderText({
    paste0("$", format(round(sum(filtered_customers()$total_balance, na.rm = TRUE)), big.mark = ","))
  })
  
  output$at_risk_customers <- renderText({
    at_risk <- sum(filtered_customers()$RELATIONSHIP_STATUS == "AT_RISK", na.rm = TRUE)
    format(at_risk, big.mark = ",")
  })
  
  # Risk distribution plot
  output$risk_distribution <- renderPlotly({
    p <- filtered_customers() |>
      count(RISK_RATING) |>
      plot_ly(labels = ~RISK_RATING, values = ~n, type = "pie",
              marker = list(colors = c("#2ecc71", "#f39c12", "#e74c3c"))) |>
      layout(title = "")
    p
  })
  
  # Balance distribution
  output$balance_distribution <- renderPlotly({
    p <- filtered_customers() |>
      ggplot(aes(x = total_balance)) +
      geom_histogram(bins = 30, fill = "#3498db", alpha = 0.7) +
      scale_x_continuous(labels = scales::dollar) +
      labs(x = "Total Balance", y = "Count") +
      theme_minimal()
    ggplotly(p)
  })
  
  # Age distribution
  output$age_distribution <- renderPlotly({
    p <- filtered_customers() |>
      ggplot(aes(x = age, fill = CUSTOMER_TYPE)) +
      geom_density(alpha = 0.6) +
      labs(x = "Age (years)", y = "Density", fill = "Customer Type") +
      theme_minimal()
    ggplotly(p)
  })
  
  # Transactions table
  output$transactions_table <- renderDT({
    transactions |>
      left_join(accounts |> select(ACCOUNT_NUMBER, CIF_NUMBER), by = "ACCOUNT_NUMBER") |>
      left_join(customers |> select(CIF_NUMBER, FULL_LEGAL_NAME), by = "CIF_NUMBER") |>
      select(TRANSACTION_ID, FULL_LEGAL_NAME, TRANSACTION_TIMESTAMP, 
             TRANSACTION_TYPE, TRANSACTION_AMOUNT, MERCHANT_NAME, CHANNEL_NAME) |>
      arrange(desc(TRANSACTION_TIMESTAMP)) |>
      head(100) |>
      datatable(options = list(pageLength = 10, scrollX = TRUE))
  })
  
  # Channel volume
  output$channel_volume <- renderPlotly({
    p <- transactions |>
      count(CHANNEL_NAME) |>
      plot_ly(x = ~CHANNEL_NAME, y = ~n, type = "bar",
              marker = list(color = "#3498db")) |>
      layout(xaxis = list(title = "Channel"),
             yaxis = list(title = "Transaction Count"))
    p
  })
  
  # Merchant amounts
  output$merchant_amounts <- renderPlotly({
    p <- transactions |>
      group_by(MERCHANT_NAME) |>
      summarise(total = sum(TRANSACTION_AMOUNT), .groups = "drop") |>
      arrange(desc(total)) |>
      head(10) |>
      plot_ly(x = ~reorder(MERCHANT_NAME, total), y = ~total, type = "bar",
              marker = list(color = "#2ecc71")) |>
      layout(xaxis = list(title = ""),
             yaxis = list(title = "Total Amount ($)"))
    p
  })
  
  # Credit risk predictions
  output$credit_risk_plot <- renderPlotly({
    # Make predictions on filtered data
    pred_data <- filtered_customers() |>
      mutate(
        is_business = ifelse(CUSTOMER_TYPE == "BUSINESS", 1, 0),
        kyc_expired = ifelse(KYC_STATUS == "EXPIRED", 1, 0)
      ) |>
      select(CREDIT_BUREAU_SCORE, age, is_business, total_accounts, 
             total_balance, kyc_expired, RISK_RATING) |>
      filter(!is.na(CREDIT_BUREAU_SCORE))
    
    if (nrow(pred_data) > 0) {
      preds <- predict(credit_model, pred_data)
      
      p <- preds |>
        count(.pred_class) |>
        plot_ly(labels = ~.pred_class, values = ~n, type = "pie") |>
        layout(title = "")
      p
    }
  })
  
  # Churn risk predictions
  output$churn_risk_plot <- renderPlotly({
    pred_data <- filtered_customers() |>
      mutate(
        is_business = ifelse(CUSTOMER_TYPE == "BUSINESS", 1, 0),
        relationship_length = as.numeric(difftime(Sys.Date(), RELATIONSHIP_OPEN_DATE, units = "days")) / 365.25
      ) |>
      select(age, relationship_length, is_business, total_accounts, 
             avg_balance, CREDIT_BUREAU_SCORE) |>
      mutate(
        closed_accounts = 0,
        total_transactions = 0
      ) |>
      filter(!is.na(age))
    
    if (nrow(pred_data) > 0) {
      preds <- predict(churn_model, pred_data, type = "prob")
      
      p <- data.frame(churn_prob = preds$.pred_Yes) |>
        ggplot(aes(x = churn_prob)) +
        geom_histogram(bins = 30, fill = "#e74c3c", alpha = 0.7) +
        labs(x = "Churn Probability", y = "Count") +
        theme_minimal()
      ggplotly(p)
    }
  })
  
  # High risk customers table
  output$high_risk_table <- renderDT({
    filtered_customers() |>
      filter(RISK_RATING == "HIGH" | RELATIONSHIP_STATUS == "AT_RISK") |>
      select(CIF_NUMBER, FULL_LEGAL_NAME, CUSTOMER_TYPE, RISK_RATING, 
             RELATIONSHIP_STATUS, CREDIT_BUREAU_SCORE, total_balance) |>
      arrange(desc(total_balance)) |>
      datatable(options = list(pageLength = 10))
  })
  
  # Branch table
  output$branch_table <- renderDT({
    branch_metrics <- accounts |>
      group_by(BRANCH_NUMBER) |>
      summarise(
        total_accounts = n(),
        total_balance = sum(CURRENT_BALANCE, na.rm = TRUE),
        avg_balance = mean(CURRENT_BALANCE, na.rm = TRUE),
        .groups = "drop"
      ) |>
      left_join(branches |> select(BRANCH_NUMBER, BRANCH_NAME, CITY, STATE_CODE, REGION_NAME), 
                by = "BRANCH_NUMBER") |>
      arrange(desc(total_balance))
    
    datatable(branch_metrics, options = list(pageLength = 10))
  })
  
  # Branch region plot
  output$branch_region_plot <- renderPlotly({
    p <- branches |>
      left_join(
        customers |> count(PRIMARY_BRANCH_NUMBER, name = "customers"),
        by = c("BRANCH_NUMBER" = "PRIMARY_BRANCH_NUMBER")
      ) |>
      group_by(REGION_NAME) |>
      summarise(total_customers = sum(customers, na.rm = TRUE), .groups = "drop") |>
      plot_ly(x = ~REGION_NAME, y = ~total_customers, type = "bar",
              marker = list(color = "#9b59b6")) |>
      layout(xaxis = list(title = "Region"),
             yaxis = list(title = "Number of Customers"))
    p
  })
}

# Run app
shinyApp(ui, server)
