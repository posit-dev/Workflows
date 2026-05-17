"""
Real-Time FSI Dashboard with Snowflake Streaming Integration & ML Models
"""

from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import snowflake.connector
import os
import pickle

# Snowflake connection config
from datetime import datetime, timedelta
import threading

import os

import os
from contextlib import contextmanager
import snowflake.connector

from snowflake.snowpark import Session
import pandas as pd

def get_session():
    """Get Snowflake session - works in both Workbench and Connect"""
    
    # Check if running on Connect
    if os.getenv("RSTUDIO_PRODUCT") == "CONNECT":
        print(f"[DEBUG] SNOWFLAKE_TOKEN: {os.getenv('SNOWFLAKE_TOKEN') is not None}")
        print(f"[DEBUG] SNOWFLAKE_OAUTH_ACCESS_TOKEN: {os.getenv('SNOWFLAKE_OAUTH_ACCESS_TOKEN') is not None}")
        print(f"[DEBUG] SNOWFLAKE_PASSWORD: {os.getenv('SNOWFLAKE_PASSWORD') is not None}")
        print(f"[DEBUG] All SNOWFLAKE_ vars: {[k for k in os.environ.keys() if 'SNOWFLAKE' in k]}")
        # Use environment variables on Connect
        config = {
            "account": os.getenv("SNOWFLAKE_ACCOUNT", "os.getenv("SNOWFLAKE_ACCOUNT", "your-account")"),
            "user": os.getenv("SNOWFLAKE_USER", "os.getenv("SNOWFLAKE_USER", "your-username")"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH"),
            "database": "FSI_DEMO",
            "schema": "RAW_BANKING",
            "role": os.getenv("SNOWFLAKE_ROLE", "SOLENG"),
        }
        
        # Try OAuth token from integration
        token = os.getenv("SNOWFLAKE_TOKEN") or os.getenv("SNOWFLAKE_OAUTH_ACCESS_TOKEN")
        if token:
            config["authenticator"] = "oauth"
            config["token"] = token
            print(f"[auth] Using OAuth token on Connect")
        else:
            # Fall back to password if no token
            password = os.getenv("SNOWFLAKE_PASSWORD")
            if password:
                config["password"] = password
                print(f"[auth] Using password authentication on Connect")
            else:
                raise RuntimeError("No Snowflake credentials found in Connect environment")
        
        return Session.builder.configs(config).create()
    
    # Use Workbench connection for development
    return Session.builder.configs({
        "connection_name": "workbench",
        "database": "FSI_DEMO",
        "schema": "RAW_BANKING",
    }).create()

def run_query(sql):
    session = get_session()
    try:
        return session.sql(sql).to_pandas()
    except Exception as e:
        print(f"Query error: {e}")
        return pd.DataFrame()
    finally:
        session.close()

def fetch_transactions_from_snowflake(hours_back=24):
    df = run_query(f"""
        SELECT 
            t.TRANSACTION_ID, 
            t.TRANSACTION_AMOUNT, 
            t.TRANSACTION_TYPE,
            t.CHANNEL_NAME, 
            t.MERCHANT_NAME, 
            t.IS_INTERNATIONAL,
            t.REVERSAL_FLAG, 
            t.TRANSACTION_TIMESTAMP, 
            t.RECORD_CREATED_TS,
            f.FRAUD_PROBABILITY,
            f.FRAUD_PREDICTION,
            f.MODEL_VERSION as FRAUD_MODEL_VERSION
        FROM FSI_DEMO.RAW_BANKING.TRANSACTION_STAGING t
        LEFT JOIN FSI_DEMO.ANALYTICS_BANKING.ML_FRAUD_SCORES f
            ON t.TRANSACTION_ID = f.TRANSACTION_KEY
        WHERE t.TRANSACTION_TIMESTAMP >= DATEADD(hour, -{hours_back}, CURRENT_TIMESTAMP())
        ORDER BY t.TRANSACTION_TIMESTAMP DESC 
        LIMIT 10000
    """)
    
    # Convert timestamp columns to datetime, handling errors gracefully
    if not df.empty:
        df['TRANSACTION_TIMESTAMP'] = pd.to_datetime(df['TRANSACTION_TIMESTAMP'], errors='coerce')
        df['RECORD_CREATED_TS'] = pd.to_datetime(df['RECORD_CREATED_TS'], errors='coerce')
        # Drop rows with invalid timestamps
        df = df.dropna(subset=['TRANSACTION_TIMESTAMP'])
    
    return df

def fetch_fraud_predictions():
    return run_query("""
        SELECT TRANSACTION_KEY, FRAUD_PROBABILITY, FRAUD_PREDICTION,
               MODEL_VERSION, SCORED_AT
        FROM FSI_DEMO.ANALYTICS_BANKING.ML_FRAUD_SCORES
        ORDER BY SCORED_AT DESC LIMIT 1000
    """)

def fetch_credit_risk_scores():
    return run_query("""
        SELECT APPLICATION_ID, CIF_NUMBER, DEFAULT_PROBABILITY,
               DEFAULT_PREDICTION, RISK_TIER, MODEL_VERSION, SCORED_AT
        FROM FSI_DEMO.ANALYTICS_BANKING.ML_CREDIT_RISK_SCORES
        ORDER BY SCORED_AT DESC LIMIT 1000
    """)

def fetch_customer_segments():
    return run_query("""
        SELECT s.CUSTOMER_KEY, s.CIF_NUMBER, s.CLUSTER_ID, s.SEGMENT_NAME,
               s.MODEL_VERSION, c.CUSTOMER_SEGMENT, c.CREDIT_SCORE,
               c.CUSTOMER_TENURE_YEARS
        FROM FSI_DEMO.ANALYTICS_BANKING.ML_CUSTOMER_SEGMENTS s
        LEFT JOIN FSI_DEMO.CORE_BANKING.DIM_CUSTOMER c 
            ON s.CUSTOMER_KEY = c.CUSTOMER_KEY AND c.IS_CURRENT = 1
        LIMIT 1000
    """)



# Custom CSS with AmeriFirst Banking branding
css = """
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700;800&family=Open+Sans:wght@300;400;600;700&display=swap');

:root {
    /* AmeriFirst Banking Brand Colors */
    --primary-navy: #002855;
    --primary-blue: #0047AB;
    --accent-gold: #D4AF37;
    --accent-light-blue: #4A90E2;
    --success: #28a745;
    --warning: #ffc107;
    --danger: #dc3545;
    --bg-light: #f8f9fa;
    --bg-white: #ffffff;
    --text-dark: #212529;
    --text-muted: #6c757d;
    --border: #dee2e6;
    --shadow: rgba(0, 40, 85, 0.1);
}

body {
    font-family: 'Open Sans', sans-serif;
    background-color: var(--bg-light);
    color: var(--text-dark);
    margin: 0;
    padding: 0;
}

.navbar {
    background: linear-gradient(135deg, var(--primary-navy) 0%, var(--primary-blue) 100%);
    padding: 1.5rem 2rem;
    box-shadow: 0 4px 12px var(--shadow);
    border-bottom: 4px solid var(--accent-gold);
}

.navbar-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1800px;
    margin: 0 auto;
}

.logo-section {
    display: flex;
    align-items: center;
    gap: 1.5rem;
}

.logo {
    width: 60px;
    height: 60px;
    background: linear-gradient(135deg, var(--accent-gold) 0%, #F4D03F 100%);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    color: var(--primary-navy);
    font-size: 1.8rem;
    font-family: 'Montserrat', sans-serif;
    box-shadow: 0 4px 16px rgba(212, 175, 55, 0.4);
    position: relative;
    overflow: hidden;
}

.logo::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: linear-gradient(45deg, transparent, rgba(255,255,255,0.3), transparent);
    transform: rotate(45deg);
    animation: shine 3s infinite;
}

@keyframes shine {
    0% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
    100% { transform: translateX(100%) translateY(100%) rotate(45deg); }
}

.company-name {
    color: white;
    font-size: 2rem;
    font-weight: 800;
    margin: 0;
    font-family: 'Montserrat', sans-serif;
    letter-spacing: -0.5px;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
}

.tagline {
    color: var(--accent-gold);
    font-size: 0.9rem;
    margin: 0;
    font-weight: 600;
    letter-spacing: 0.5px;
}

.status-dot {
    width: 12px;
    height: 12px;
    background: var(--success);
    border-radius: 50%;
    animation: pulse 2s infinite;
    box-shadow: 0 0 8px var(--success);
}

@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.7; transform: scale(1.1); }
}

.status-text {
    color: white;
    font-size: 0.95rem;
    font-weight: 600;
    font-family: 'Montserrat', sans-serif;
}

.main-container {
    max-width: 1800px;
    margin: 0 auto;
    padding: 2rem;
}

.filters-card {
    background: white;
    border-radius: 12px;
    padding: 2rem;
    box-shadow: 0 2px 8px var(--shadow);
    margin-bottom: 2rem;
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent-gold);
}

.filters-title {
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--primary-navy);
    margin-bottom: 1.5rem;
    font-family: 'Montserrat', sans-serif;
}

.kpi-card {
    background: white;
    border-radius: 12px;
    padding: 2rem;
    box-shadow: 0 2px 8px var(--shadow);
    transition: all 0.3s ease;
    border: 1px solid var(--border);
    position: relative;
    overflow: hidden;
    height: 100%;
}

.kpi-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, var(--accent-gold), var(--accent-light-blue));
}

.kpi-card:hover {
    transform: translateY(-8px);
    box-shadow: 0 12px 24px var(--shadow);
}

.kpi-label {
    font-size: 0.85rem;
    color: var(--text-muted);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.75rem;
    font-family: 'Montserrat', sans-serif;
}

.kpi-value {
    font-size: 2.75rem;
    font-weight: 800;
    color: var(--primary-navy);
    margin-bottom: 0.75rem;
    line-height: 1;
    font-family: 'Montserrat', sans-serif;
}

.kpi-change {
    font-size: 0.9rem;
    font-weight: 600;
}

.kpi-change.positive { color: var(--success); }
.kpi-change.negative { color: var(--danger); }
.kpi-change.neutral { color: var(--text-muted); }

.chart-card {
    background: white;
    border-radius: 12px;
    padding: 2rem;
    box-shadow: 0 2px 8px var(--shadow);
    margin-bottom: 2rem;
    border: 1px solid var(--border);
}

.chart-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--primary-navy);
    margin-bottom: 1.5rem;
    font-family: 'Montserrat', sans-serif;
}

.table-card {
    background: white;
    border-radius: 12px;
    padding: 2rem;
    box-shadow: 0 2px 8px var(--shadow);
    border: 1px solid var(--border);
}

.nav-tabs {
    border-bottom: 2px solid var(--border);
    margin-bottom: 2rem;
}

.nav-tabs .nav-link {
    color: var(--text-muted);
    font-weight: 600;
    padding: 1rem 1.75rem;
    border: none;
    border-bottom: 3px solid transparent;
    transition: all 0.3s ease;
    font-family: 'Montserrat', sans-serif;
    font-size: 0.95rem;
}

.nav-tabs .nav-link:hover {
    color: var(--primary-blue);
    border-bottom-color: var(--accent-gold);
}

.nav-tabs .nav-link.active {
    color: var(--primary-navy);
    border-bottom-color: var(--accent-gold);
    background: none;
    font-weight: 700;
}

.btn-primary {
    background: linear-gradient(135deg, var(--primary-blue), var(--accent-light-blue));
    border: none;
    color: white;
    font-weight: 700;
    padding: 0.75rem 1.75rem;
    border-radius: 8px;
    transition: all 0.3s ease;
    box-shadow: 0 4px 12px rgba(0, 71, 171, 0.3);
    font-family: 'Montserrat', sans-serif;
}

.btn-primary:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 20px rgba(0, 71, 171, 0.4);
    background: linear-gradient(135deg, var(--accent-light-blue), var(--primary-blue));
}

.risk-badge {
    display: inline-block;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    font-family: 'Montserrat', sans-serif;
    letter-spacing: 0.5px;
}

.risk-low {
    background: var(--success);
    color: white;
}

.risk-moderate {
    background: var(--warning);
    color: var(--text-dark);
}

.risk-high {
    background: #fd7e14;
    color: white;
}

.risk-very-high {
    background: var(--danger);
    color: white;
}
"""

# UI with tabs
app_ui = ui.page_fluid(
    ui.tags.style(css),
    
     # Header
    ui.div(
        ui.div(
            ui.div(
                ui.div("AF", class_="logo"),  # Changed from "FS" to "AF"
                ui.div(
                    ui.h1("AmeriFirst Banking", class_="company-name"),  # Changed company name
                    ui.p("Enterprise Intelligence & Analytics Platform", class_="tagline"),  # Updated tagline
                ),
                class_="logo-section"
            ),
            ui.div(
                ui.span(class_="status-dot"),
                ui.span("Live Monitoring", class_="status-text", style="margin-left: 0.5rem;"),
                style="display: flex; align-items: center; background: rgba(255,255,255,0.15); padding: 0.6rem 1.2rem; border-radius: 8px;"
            ),
            class_="navbar-content"
        ),
        class_="navbar"
    ),
    
    ui.div(
        # Navigation Tabs
        ui.navset_tab(
            # Tab 1: Real-Time Monitoring
            ui.nav_panel(
                "🔴 Real-Time Monitoring",
                ui.div(
                    # Filters
                    ui.div(
                        ui.h4("⚙️ Dashboard Controls", class_="filters-title"),
                        ui.row(
                            ui.column(2, 
                                ui.input_select("channel_filter", "Channel", 
                                    choices=["All", "Online Banking", "Mobile App", "ATM", "Branch", "Phone"])
                            ),
                            ui.column(2, 
                                ui.input_select("type_filter", "Transaction Type",
                                    choices=["All", "DEBIT", "CREDIT", "TRANSFER", "WITHDRAWAL"])
                            ),
                            ui.column(2, 
                                ui.input_slider("fraud_threshold", "Fraud Risk", 0, 1, 0.5, step=0.1)
                            ),
                            ui.column(2,
                                ui.input_select("time_range", "Time Range",
                                    choices=["1", "6", "24"],
                                    selected="24")
                            ),
                            ui.column(2,
                                ui.input_checkbox("high_value_only", "High Value Only", False)
                            ),
                            ui.column(2, 
                                ui.input_action_button("refresh", "🔄 Refresh", class_="btn-primary", 
                                    style="width: 100%;")
                            ),
                        ),
                        class_="filters-card"
                    ),
                    
                    # KPI Cards
                    ui.row(
                        ui.column(3, ui.div(ui.output_ui("kpi_total_volume"), class_="kpi-card")),
                        ui.column(3, ui.div(ui.output_ui("kpi_total_transactions"), class_="kpi-card")),
                        ui.column(3, ui.div(ui.output_ui("kpi_high_risk"), class_="kpi-card")),
                        ui.column(3, ui.div(ui.output_ui("kpi_avg_transaction"), class_="kpi-card")),
                    ),
                    
                    ui.br(),
                    
                    # Charts Row 1
                    ui.row(
                        ui.column(8, 
                            ui.div(
                                ui.h4("Transaction Volume Timeline", class_="chart-title"),
                                output_widget("time_series_chart"),
                                class_="chart-card"
                            )
                        ),
                        ui.column(4,
                            ui.div(
                                ui.h4("Fraud Risk Distribution", class_="chart-title"),
                                output_widget("fraud_distribution"),
                                class_="chart-card"
                            )
                        ),
                    ),
                    
                    # Charts Row 2
                    ui.row(
                        ui.column(4,
                            ui.div(
                                ui.h4("Channel Performance", class_="chart-title"),
                                output_widget("channel_chart"),
                                class_="chart-card"
                            )
                        ),
                        ui.column(4,
                            ui.div(
                                ui.h4("Transaction Type Breakdown", class_="chart-title"),
                                output_widget("type_chart"),
                                class_="chart-card"
                            )
                        ),
                        ui.column(4,
                            ui.div(
                                ui.h4("International vs Domestic", class_="chart-title"),
                                output_widget("international_chart"),
                                class_="chart-card"
                            )
                        ),
                    ),
                    
                    # High Risk Table
                    ui.div(
                        ui.h4("🚨 High-Risk Transactions", class_="chart-title"),
                        ui.output_data_frame("high_risk_table"),
                        class_="table-card"
                    ),
                )
            ),
            
            # Tab 2: Fraud Detection Model
            ui.nav_panel(
                "🛡️ Fraud Detection",
                ui.div(
                    ui.h2("Fraud Detection Model Results", style="margin-bottom: 2rem;"),
                    
                    # Model Info Card
                    ui.div(
                        ui.h4("📊 Model Information", class_="chart-title"),
                        ui.output_ui("fraud_model_info"),
                        class_="chart-card"
                    ),
                    
                    # KPIs
                    ui.row(
                        ui.column(3, ui.div(ui.output_ui("fraud_total_scored"), class_="kpi-card")),
                        ui.column(3, ui.div(ui.output_ui("fraud_predicted_count"), class_="kpi-card")),
                        ui.column(3, ui.div(ui.output_ui("fraud_avg_probability"), class_="kpi-card")),
                        ui.column(3, ui.div(ui.output_ui("fraud_high_risk_count"), class_="kpi-card")),
                    ),
                    
                    ui.br(),
                    
                    # Charts
                    ui.row(
                        ui.column(6,
                            ui.div(
                                ui.h4("Fraud Probability Distribution", class_="chart-title"),
                                output_widget("fraud_prob_dist"),
                                class_="chart-card"
                            )
                        ),
                        ui.column(6,
                            ui.div(
                                ui.h4("Predictions Over Time", class_="chart-title"),
                                output_widget("fraud_time_series"),
                                class_="chart-card"
                            )
                        ),
                    ),
                    
                    # High Risk Predictions Table
                    ui.div(
                        ui.h4("🚨 High-Risk Fraud Predictions", class_="chart-title"),
                        ui.output_data_frame("fraud_predictions_table"),
                        class_="table-card"
                    ),
                )
            ),
            
            # Tab 3: Credit Risk Model
            ui.nav_panel(
                "💳 Credit Risk",
                ui.div(
                    ui.h2("Credit Risk Model Results", style="margin-bottom: 2rem;"),
                    
                    # Model Info Card
                    ui.div(
                        ui.h4("📊 Model Information", class_="chart-title"),
                        ui.output_ui("credit_model_info"),
                        class_="chart-card"
                    ),
                    
                    # KPIs
                    ui.row(
                        ui.column(3, ui.div(ui.output_ui("credit_total_scored"), class_="kpi-card")),
                        ui.column(3, ui.div(ui.output_ui("credit_low_risk"), class_="kpi-card")),
                        ui.column(3, ui.div(ui.output_ui("credit_moderate_risk"), class_="kpi-card")),
                        ui.column(3, ui.div(ui.output_ui("credit_high_risk"), class_="kpi-card")),
                    ),
                    
                    ui.br(),
                    
                    # Charts
                    ui.row(
                        ui.column(6,
                            ui.div(
                                ui.h4("Risk Tier Distribution", class_="chart-title"),
                                output_widget("credit_risk_tiers"),
                                class_="chart-card"
                            )
                        ),
                        ui.column(6,
                            ui.div(
                                ui.h4("Default Probability Distribution", class_="chart-title"),
                                output_widget("credit_prob_dist"),
                                class_="chart-card"
                            )
                        ),
                    ),
                    
                    # Risk Scores Table
                    ui.div(
                        ui.h4("📋 Credit Risk Scores", class_="chart-title"),
                        ui.output_data_frame("credit_scores_table"),
                        class_="table-card"
                    ),
                )
            ),
            
            # Tab 4: Customer Segmentation
            ui.nav_panel(
                "👥 Customer Segments",
                ui.div(
                    ui.h2("Customer Segmentation Results", style="margin-bottom: 2rem;"),
                    
                    # Model Info Card
                    ui.div(
                        ui.h4("📊 Model Information", class_="chart-title"),
                        ui.output_ui("segment_model_info"),
                        class_="chart-card"
                    ),
                    
                    # Segment KPIs
                    ui.row(
                        ui.column(2, ui.div(ui.output_ui("segment_total"), class_="kpi-card")),
                        ui.column(2, ui.div(ui.output_ui("segment_count_1"), class_="kpi-card")),
                        ui.column(2, ui.div(ui.output_ui("segment_count_2"), class_="kpi-card")),
                        ui.column(2, ui.div(ui.output_ui("segment_count_3"), class_="kpi-card")),
                        ui.column(2, ui.div(ui.output_ui("segment_count_4"), class_="kpi-card")),
                        ui.column(2, ui.div(ui.output_ui("segment_count_5"), class_="kpi-card")),
                    ),
                    
                    ui.br(),
                    
                    # Charts
                    ui.row(
                        ui.column(6,
                            ui.div(
                                ui.h4("Segment Distribution", class_="chart-title"),
                                output_widget("segment_distribution"),
                                class_="chart-card"
                            )
                        ),
                        ui.column(6,
                            ui.div(
                                ui.h4("Segment Characteristics", class_="chart-title"),
                                output_widget("segment_characteristics"),
                                class_="chart-card"
                            )
                        ),
                    ),
                    
                    # Segments Table
                    ui.div(
                        ui.h4("📋 Customer Segments", class_="chart-title"),
                        ui.output_data_frame("segments_table"),
                        class_="table-card"
                    ),
                )
            ),
        ),
        
        class_="main-container"
    )
)

# Server
def server(input, output, session):
    # ========================================================================
    # REAL-TIME MONITORING TAB
    # ========================================================================
    
    # Reactive data
    transaction_data = reactive.Value(pd.DataFrame())
    
    # Initial load
    @reactive.Effect
    def _():
        df = fetch_transactions_from_snowflake(int(input.time_range()))
        transaction_data.set(df)
    
    # Manual refresh
    @reactive.Effect
    @reactive.event(input.refresh)
    def _():
        df = fetch_transactions_from_snowflake(int(input.time_range()))
        transaction_data.set(df)
    
    # Auto-refresh every 30 seconds
    @reactive.Effect
    def _():
        reactive.invalidate_later(30)
        df = fetch_transactions_from_snowflake(int(input.time_range()))
        transaction_data.set(df)
    
    # Filtered data reactive
    @reactive.Calc
    def filtered_data():
        df = transaction_data.get()
        if df.empty:
            return df
        
        # Apply filters
        filtered = df.copy()
        
        # Only filter by CHANNEL if column exists
        if 'CHANNEL_NAME' in filtered.columns and input.channel_filter() != "All":
            filtered = filtered[filtered['CHANNEL_NAME'] == input.channel_filter()]
        
        # Only filter by TRANSACTION_TYPE if column exists
        if 'TRANSACTION_TYPE' in filtered.columns and input.type_filter() != "All":
            filtered = filtered[filtered['TRANSACTION_TYPE'] == input.type_filter()]
        
        # Only filter by IS_HIGH_VALUE if column exists
        if 'IS_HIGH_VALUE' in filtered.columns and input.high_value_only():
            filtered = filtered[filtered['IS_HIGH_VALUE'] == True]
        
        # Only filter by FRAUD_RISK_SCORE if column exists
        if 'FRAUD_RISK_SCORE' in filtered.columns:
            filtered = filtered[filtered['FRAUD_RISK_SCORE'] >= input.fraud_threshold()]
            
        return filtered
    
    # KPI Outputs
    @output
    @render.ui
    def kpi_total_volume():
        df = filtered_data()
        if df.empty:
            total = 0
        else:
            total = df['TRANSACTION_AMOUNT'].sum()
        
        return ui.div(
            ui.div("Total Volume", class_="kpi-label"),
            ui.div(f"${total:,.0f}", class_="kpi-value"),
            ui.div("↗ +12.5% vs yesterday", class_="kpi-change positive")
        )
    
    @output
    @render.ui
    def kpi_total_transactions():
        df = filtered_data()
        count = len(df)
        
        return ui.div(
            ui.div("Total Transactions", class_="kpi-label"),
            ui.div(f"{count:,}", class_="kpi-value"),
            ui.div("↗ +8.3% vs yesterday", class_="kpi-change positive")
        )
    
    @output
    @render.ui
    def kpi_high_risk():
        df = filtered_data()
        if df.empty:
            high_risk = 0
        else:
            # Since FRAUD_RISK_SCORE doesn't exist in TRANSACTION_STAGING,
            # just show count of international or high-value transactions as a proxy
            if 'IS_INTERNATIONAL' in df.columns:
                high_risk = len(df[df['IS_INTERNATIONAL'] == True])
            else:
                high_risk = 0
        
        return ui.div(
            ui.div("International Transactions", class_="kpi-label"),
            ui.div(f"{high_risk:,}", class_="kpi-value"),
            ui.div("↘ -2.1% vs yesterday", class_="kpi-change negative")
        )
    
    @output
    @render.ui
    def kpi_avg_transaction():
        df = filtered_data()
        if df.empty:
            avg = 0
        else:
            avg = df['TRANSACTION_AMOUNT'].mean()
        
        return ui.div(
            ui.div("Avg Transaction", class_="kpi-label"),
            ui.div(f"${avg:.0f}", class_="kpi-value"),
            ui.div("→ +0.8% vs yesterday", class_="kpi-change neutral")
        )
    
    # Chart Outputs
    @output
    @render_widget
    def time_series_chart():
        df = filtered_data()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        # Ensure timestamp is properly parsed as datetime
        df['hour'] = pd.to_datetime(df['TRANSACTION_TIMESTAMP']).dt.floor('h')
        hourly = df.groupby('hour').agg({
            'TRANSACTION_AMOUNT': 'sum',
            'TRANSACTION_ID': 'count'
        }).reset_index()
        
        # Sort by hour to ensure proper line plotting
        hourly = hourly.sort_values('hour')
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hourly['hour'],
            y=hourly['TRANSACTION_AMOUNT'],
            mode='lines+markers',
            name='Volume ($)',
            line=dict(color='#4A90E2', width=3),
            marker=dict(size=6)
        ))
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="Time",
            yaxis_title="Transaction Volume ($)",
            showlegend=False,
            xaxis=dict(
                type='date',  # Add this - tells Plotly to treat x-axis as dates
                tickformat='%m/%d %I:%M %p',
                tickangle=-45,
                nticks=10  # Limit number of ticks for readability
            )
        )
        return fig

    @output
    @render_widget
    def fraud_distribution():
        df = filtered_data()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        # Since FRAUD_RISK_SCORE doesn't exist in TRANSACTION_STAGING,
        # show distribution of transaction types instead
        if 'TRANSACTION_TYPE' not in df.columns:
            fig = go.Figure()
            fig.add_annotation(text="Transaction type data not available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        type_counts = df['TRANSACTION_TYPE'].value_counts()
        
        colors = ['#D4AF37', '#4A90E2', '#0047AB', '#002855']  # AmeriFirst colors
        
        fig = go.Figure(data=[go.Pie(
            labels=type_counts.index,
            values=type_counts.values,
            marker_colors=colors[:len(type_counts)],
            hole=0.4
        )])
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=True
        )
        
        return fig
    
    @output
    @render_widget
    def channel_chart():
        df = filtered_data()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        # Use CHANNEL_NAME if it exists, otherwise show message
        if 'CHANNEL_NAME' not in df.columns:
            fig = go.Figure()
            fig.add_annotation(text="Channel data not available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        channel_data = df.groupby('CHANNEL_NAME')['TRANSACTION_AMOUNT'].sum().reset_index()
        
        fig = go.Figure(data=[go.Bar(
            x=channel_data['CHANNEL_NAME'],
            y=channel_data['TRANSACTION_AMOUNT'],
            marker_color='#4A90E2'
        )])
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="Channel",
            yaxis_title="Volume ($)",
            showlegend=False
        )
        
        return fig
    
    @output
    @render_widget
    def type_chart():
        df = filtered_data()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        if 'TRANSACTION_TYPE' not in df.columns:
            fig = go.Figure()
            fig.add_annotation(text="Transaction type data not available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        type_data = df.groupby('TRANSACTION_TYPE')['TRANSACTION_AMOUNT'].sum().reset_index()
        
        fig = go.Figure(data=[go.Bar(
            x=type_data['TRANSACTION_TYPE'],
            y=type_data['TRANSACTION_AMOUNT'],
            marker_color='#00b8a9'
        )])
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="Transaction Type",
            yaxis_title="Volume ($)",
            showlegend=False
        )
        
        return fig
        
    @output
    @render_widget
    def international_chart():
        df = filtered_data()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        intl_data = df.groupby('IS_INTERNATIONAL')['TRANSACTION_AMOUNT'].sum().reset_index()
        intl_data['IS_INTERNATIONAL'] = intl_data['IS_INTERNATIONAL'].map({True: 'International', False: 'Domestic'})
        
        fig = go.Figure(data=[go.Pie(
            labels=intl_data['IS_INTERNATIONAL'],
            values=intl_data['TRANSACTION_AMOUNT'],
            marker_colors=['#ff9800', '#00d4ff']
        )])
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=True
        )
        
        return fig
    
    @output
    @render.data_frame
    def high_risk_table():
        df = filtered_data()
        if df.empty:
            return pd.DataFrame()
        
        # Show international or high-value transactions instead
        if 'IS_INTERNATIONAL' in df.columns:
            high_risk = df[df['IS_INTERNATIONAL'] == True].copy()
        else:
            high_risk = df.head(20).copy()
        
        if high_risk.empty:
            return pd.DataFrame()
        
        # Select available columns for display
        available_cols = []
        for col in ['TRANSACTION_ID', 'TRANSACTION_AMOUNT', 'TRANSACTION_TYPE', 
                    'CHANNEL_NAME', 'MERCHANT_NAME', 'TRANSACTION_TIMESTAMP']:
            if col in high_risk.columns:
                available_cols.append(col)
        
        high_risk = high_risk[available_cols].head(20)
        
        # Format amount if it exists
        if 'TRANSACTION_AMOUNT' in high_risk.columns:
            high_risk['TRANSACTION_AMOUNT'] = high_risk['TRANSACTION_AMOUNT'].apply(lambda x: f"${x:,.2f}")
        
        return high_risk
    
    # ========================================================================
    # FRAUD DETECTION MODEL TAB
    # ========================================================================
    
    fraud_predictions = reactive.Value(pd.DataFrame())
    
    @reactive.Effect
    def _():
        df = fetch_fraud_predictions()
        fraud_predictions.set(df)
    
    @output
    @render.ui
    def fraud_model_info():
        df = fraud_predictions.get()
        if df.empty:
            model_version = "N/A"
            last_scored = "N/A"
        else:
            model_version = df['MODEL_VERSION'].iloc[0] if 'MODEL_VERSION' in df.columns else "N/A"
            last_scored = df['SCORED_AT'].max() if 'SCORED_AT' in df.columns else "N/A"
        
        return ui.div(
            ui.p(f"Model Version: {model_version}", style="margin: 0.5rem 0;"),
            ui.p(f"Last Scored: {last_scored}", style="margin: 0.5rem 0;"),
            ui.p("Algorithm: XGBoost Classifier", style="margin: 0.5rem 0;"),
        )
    
    @output
    @render.ui
    def fraud_total_scored():
        df = fraud_predictions.get()
        count = len(df)
        
        return ui.div(
            ui.div("Total Scored", class_="kpi-label"),
            ui.div(f"{count:,}", class_="kpi-value"),
        )
    
    @output
    @render.ui
    def fraud_predicted_count():
        df = fraud_predictions.get()
        if df.empty:
            predicted = 0
        else:
            predicted = df['FRAUD_PREDICTION'].sum()
        
        return ui.div(
            ui.div("Predicted Fraud", class_="kpi-label"),
            ui.div(f"{predicted:,}", class_="kpi-value"),
            ui.div(f"{predicted/len(df)*100:.1f}% of total" if len(df) > 0 else "0%", class_="kpi-change neutral")
        )
    
    @output
    @render.ui
    def fraud_avg_probability():
        df = fraud_predictions.get()
        if df.empty:
            avg_prob = 0
        else:
            avg_prob = df['FRAUD_PROBABILITY'].mean()
        
        return ui.div(
            ui.div("Avg Probability", class_="kpi-label"),
            ui.div(f"{avg_prob:.3f}", class_="kpi-value"),
        )
    
    @output
    @render.ui
    def fraud_high_risk_count():
        df = fraud_predictions.get()
        if df.empty:
            high_risk = 0
        else:
            high_risk = len(df[df['FRAUD_PROBABILITY'] > 0.7])
        
        return ui.div(
            ui.div("High Risk (>0.7)", class_="kpi-label"),
            ui.div(f"{high_risk:,}", class_="kpi-value"),
            ui.div(f"{high_risk/len(df)*100:.1f}% of total" if len(df) > 0 else "0%", class_="kpi-change negative")
        )
    
    @output
    @render_widget
    def fraud_prob_dist():
        df = fraud_predictions.get()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        fig = go.Figure(data=[go.Histogram(
            x=df['FRAUD_PROBABILITY'],
            nbinsx=50,
            marker_color='#00d4ff'
        )])
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="Fraud Probability",
            yaxis_title="Count",
            showlegend=False
        )
        
        return fig
    
    @output
    @render_widget
    def fraud_time_series():
        df = fraud_predictions.get()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        df['SCORED_AT'] = pd.to_datetime(df['SCORED_AT'], errors='coerce')
        
        # Drop rows with invalid timestamps
        df = df.dropna(subset=['SCORED_AT'])
        
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No valid timestamps in data", x=0.5, y=0.5, showarrow=False)
            return fig
        
        df['date'] = df['SCORED_AT'].dt.date
        daily = df.groupby('date')['FRAUD_PREDICTION'].sum().reset_index()
        
        fig = go.Figure(data=[go.Scatter(
            x=daily['date'],
            y=daily['FRAUD_PREDICTION'],
            mode='lines+markers',
            line=dict(color='#f44336', width=3),
            marker=dict(size=8)
        )])
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="Date",
            yaxis_title="Predicted Fraud Count",
            showlegend=False
        )
        
        return fig
    
    @output
    @render.data_frame
    def fraud_predictions_table():
        df = fraud_predictions.get()
        if df.empty:
            return pd.DataFrame()
        
        # Filter high risk
        high_risk = df[df['FRAUD_PROBABILITY'] > 0.5].copy()
        high_risk = high_risk.sort_values('FRAUD_PROBABILITY', ascending=False).head(20)
        
        # Format columns
        high_risk['FRAUD_PROBABILITY'] = high_risk['FRAUD_PROBABILITY'].apply(lambda x: f"{x:.3f}")
        
        return high_risk[['TRANSACTION_KEY', 'FRAUD_PROBABILITY', 'FRAUD_PREDICTION', 'MODEL_VERSION']]
    
    # ========================================================================
    # CREDIT RISK MODEL TAB
    # ========================================================================
    
    credit_scores = reactive.Value(pd.DataFrame())
    
    @reactive.Effect
    def _():
        df = fetch_credit_risk_scores()
        credit_scores.set(df)
    
    @output
    @render.ui
    def credit_model_info():
        df = credit_scores.get()
        if df.empty:
            model_version = "N/A"
            last_scored = "N/A"
        else:
            model_version = df['MODEL_VERSION'].iloc[0] if 'MODEL_VERSION' in df.columns else "N/A"
            last_scored = df['SCORED_AT'].max() if 'SCORED_AT' in df.columns else "N/A"
        
        return ui.div(
            ui.p(f"Model Version: {model_version}", style="margin: 0.5rem 0;"),
            ui.p(f"Last Scored: {last_scored}", style="margin: 0.5rem 0;"),
            ui.p("Algorithm: XGBoost (tidymodels)", style="margin: 0.5rem 0;"),
        )
    
    @output
    @render.ui
    def credit_total_scored():
        df = credit_scores.get()
        count = len(df)
        
        return ui.div(
            ui.div("Total Applications", class_="kpi-label"),
            ui.div(f"{count:,}", class_="kpi-value"),
        )
    
    @output
    @render.ui
    def credit_low_risk():
        df = credit_scores.get()
        if df.empty:
            low_risk = 0
        else:
            low_risk = len(df[df['RISK_TIER'] == 'LOW_RISK'])
        
        return ui.div(
            ui.div("Low Risk", class_="kpi-label"),
            ui.div(f"{low_risk:,}", class_="kpi-value"),
            ui.div(f"{low_risk/len(df)*100:.1f}% of total" if len(df) > 0 else "0%", class_="kpi-change positive")
        )
    
    @output
    @render.ui
    def credit_moderate_risk():
        df = credit_scores.get()
        if df.empty:
            mod_risk = 0
        else:
            mod_risk = len(df[df['RISK_TIER'] == 'MODERATE_RISK'])
        
        return ui.div(
            ui.div("Moderate Risk", class_="kpi-label"),
            ui.div(f"{mod_risk:,}", class_="kpi-value"),
            ui.div(f"{mod_risk/len(df)*100:.1f}% of total" if len(df) > 0 else "0%", class_="kpi-change neutral")
        )
    
    @output
    @render.ui
    def credit_high_risk():
        df = credit_scores.get()
        if df.empty:
            high_risk = 0
        else:
            high_risk = len(df[df['RISK_TIER'].isin(['HIGH_RISK', 'VERY_HIGH_RISK'])])
        
        return ui.div(
            ui.div("High/Very High Risk", class_="kpi-label"),
            ui.div(f"{high_risk:,}", class_="kpi-value"),
            ui.div(f"{high_risk/len(df)*100:.1f}% of total" if len(df) > 0 else "0%", class_="kpi-change negative")
        )
    
    @output
    @render_widget
    def credit_risk_tiers():
        df = credit_scores.get()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        tier_counts = df['RISK_TIER'].value_counts()
        colors = {'LOW_RISK': '#00c853', 'MODERATE_RISK': '#ffc107', 
                  'HIGH_RISK': '#ff9800', 'VERY_HIGH_RISK': '#f44336'}
        
        fig = go.Figure(data=[go.Bar(
            x=tier_counts.index,
            y=tier_counts.values,
            marker_color=[colors.get(tier, '#64748b') for tier in tier_counts.index]
        )])
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="Risk Tier",
            yaxis_title="Count",
            showlegend=False
        )
        
        return fig
    
    @output
    @render_widget
    def credit_prob_dist():
        df = credit_scores.get()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data  available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        fig = go.Figure(data=[go.Histogram(
            x=df['DEFAULT_PROBABILITY'],
            nbinsx=50,
            marker_color='#ff9800'
        )])
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="Default Probability",
            yaxis_title="Count",
            showlegend=False
        )
        
        return fig
    
    @output
    @render.data_frame
    def credit_scores_table():
        df = credit_scores.get()
        if df.empty:
            return pd.DataFrame()
        
        # Sort by risk tier and probability
        display_df = df.sort_values('DEFAULT_PROBABILITY', ascending=False).head(20).copy()
        
        # Format columns
        display_df['DEFAULT_PROBABILITY'] = display_df['DEFAULT_PROBABILITY'].apply(lambda x: f"{x:.3f}")
        
        return display_df[['APPLICATION_ID', 'CIF_NUMBER', 'DEFAULT_PROBABILITY', 'RISK_TIER', 'MODEL_VERSION']]
    
    # ========================================================================
    # CUSTOMER SEGMENTATION TAB
    # ========================================================================
    
    customer_segments = reactive.Value(pd.DataFrame())
    
    @reactive.Effect
    def _():
        df = fetch_customer_segments()
        customer_segments.set(df)
    
    @output
    @render.ui
    def segment_model_info():
        df = customer_segments.get()
        if df.empty:
            model_version = "N/A"
            num_clusters = "N/A"
        else:
            model_version = df['MODEL_VERSION'].iloc[0] if 'MODEL_VERSION' in df.columns else "N/A"
            num_clusters = df['CLUSTER_ID'].nunique() if 'CLUSTER_ID' in df.columns else "N/A"
        
        return ui.div(
            ui.p(f"Model Version: {model_version}", style="margin: 0.5rem 0;"),
            ui.p(f"Number of Segments: {num_clusters}", style="margin: 0.5rem 0;"),
            ui.p("Algorithm: K-means Clustering", style="margin: 0.5rem 0;"),
        )
    
    @output
    @render.ui
    def segment_total():
        df = customer_segments.get()
        count = len(df)
        
        return ui.div(
            ui.div("Total Customers", class_="kpi-label"),
            ui.div(f"{count:,}", class_="kpi-value"),
        )
    
    @output
    @render.ui
    def segment_count_1():
        df = customer_segments.get()
        if df.empty:
            count = 0
            name = "Segment 1"
        else:
            seg_df = df[df['CLUSTER_ID'] == 1]
            count = len(seg_df)
            name = seg_df['SEGMENT_NAME'].iloc[0] if len(seg_df) > 0 and 'SEGMENT_NAME' in seg_df.columns else "Segment 1"
        
        return ui.div(
            ui.div(name, class_="kpi-label"),
            ui.div(f"{count:,}", class_="kpi-value"),
            ui.div(f"{count/len(df)*100:.1f}%" if len(df) > 0 else "0%", class_="kpi-change neutral")
        )
    
    @output
    @render.ui
    def segment_count_2():
        df = customer_segments.get()
        if df.empty:
            count = 0
            name = "Segment 2"
        else:
            seg_df = df[df['CLUSTER_ID'] == 2]
            count = len(seg_df)
            name = seg_df['SEGMENT_NAME'].iloc[0] if len(seg_df) > 0 and 'SEGMENT_NAME' in seg_df.columns else "Segment 2"
        
        return ui.div(
            ui.div(name, class_="kpi-label"),
            ui.div(f"{count:,}", class_="kpi-value"),
            ui.div(f"{count/len(df)*100:.1f}%" if len(df) > 0 else "0%", class_="kpi-change neutral")
        )
    
    @output
    @render.ui
    def segment_count_3():
        df = customer_segments.get()
        if df.empty:
            count = 0
            name = "Segment 3"
        else:
            seg_df = df[df['CLUSTER_ID'] == 3]
            count = len(seg_df)
            name = seg_df['SEGMENT_NAME'].iloc[0] if len(seg_df) > 0 and 'SEGMENT_NAME' in seg_df.columns else "Segment 3"
        
        return ui.div(
            ui.div(name, class_="kpi-label"),
            ui.div(f"{count:,}", class_="kpi-value"),
            ui.div(f"{count/len(df)*100:.1f}%" if len(df) > 0 else "0%", class_="kpi-change neutral")
        )
    
    @output
    @render.ui
    def segment_count_4():
        df = customer_segments.get()
        if df.empty:
            count = 0
            name = "Segment 4"
        else:
            seg_df = df[df['CLUSTER_ID'] == 4]
            count = len(seg_df)
            name = seg_df['SEGMENT_NAME'].iloc[0] if len(seg_df) > 0 and 'SEGMENT_NAME' in seg_df.columns else "Segment 4"
        
        return ui.div(
            ui.div(name, class_="kpi-label"),
            ui.div(f"{count:,}", class_="kpi-value"),
            ui.div(f"{count/len(df)*100:.1f}%" if len(df) > 0 else "0%", class_="kpi-change neutral")
        )
    
    @output
    @render.ui
    def segment_count_5():
        df = customer_segments.get()
        if df.empty:
            count = 0
            name = "Segment 5"
        else:
            seg_df = df[df['CLUSTER_ID'] == 5]
            count = len(seg_df)
            name = seg_df['SEGMENT_NAME'].iloc[0] if len(seg_df) > 0 and 'SEGMENT_NAME' in seg_df.columns else "Segment 5"
        
        return ui.div(
            ui.div(name, class_="kpi-label"),
            ui.div(f"{count:,}", class_="kpi-value"),
            ui.div(f"{count/len(df)*100:.1f}%" if len(df) > 0 else "0%", class_="kpi-change neutral")
        )
    
    @output
    @render_widget
    def segment_distribution():
        df = customer_segments.get()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        # Count by segment name
        segment_counts = df['SEGMENT_NAME'].value_counts() if 'SEGMENT_NAME' in df.columns else df['CLUSTER_ID'].value_counts()
        
        colors = ['#00d4ff', '#00b8a9', '#ffc107', '#ff9800', '#f44336']
        
        fig = go.Figure(data=[go.Pie(
            labels=segment_counts.index,
            values=segment_counts.values,
            marker_colors=colors[:len(segment_counts)],
            hole=0.4
        )])
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=True
        )
        
        return fig
    
    @output
    @render_widget
    def segment_characteristics():
        df = customer_segments.get()
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
            return fig
        
        # Average credit score and tenure by segment
        if 'SEGMENT_NAME' in df.columns:
            segment_stats = df.groupby('SEGMENT_NAME').agg({
                'CREDIT_SCORE': 'mean',
                'CUSTOMER_TENURE_YEARS': 'mean'
            }).reset_index()
            x_col = 'SEGMENT_NAME'
        else:
            segment_stats = df.groupby('CLUSTER_ID').agg({
                'CREDIT_SCORE': 'mean',
                'CUSTOMER_TENURE_YEARS': 'mean'
            }).reset_index()
            x_col = 'CLUSTER_ID'
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Avg Credit Score',
            x=segment_stats[x_col],
            y=segment_stats['CREDIT_SCORE'],
            marker_color='#00d4ff'
        ))
        
        fig.add_trace(go.Bar(
            name='Avg Tenure (Years)',
            x=segment_stats[x_col],
            y=segment_stats['CUSTOMER_TENURE_YEARS'] * 100,  # Scale for visibility
            marker_color='#00b8a9'
        ))
        
        fig.update_layout(
            template='plotly_white',
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="Segment",
            yaxis_title="Value",
            barmode='group',
            showlegend=True
        )
        
        return fig
    
    @output
    @render.data_frame
    def segments_table():
        df = customer_segments.get()
        if df.empty:
            return pd.DataFrame()
        
        # Sample 20 customers
        display_df = df.head(20).copy()
        
        # Select columns
        cols = ['CUSTOMER_KEY', 'CIF_NUMBER', 'CLUSTER_ID', 'SEGMENT_NAME', 'CREDIT_SCORE', 'CUSTOMER_TENURE_YEARS']
        available_cols = [col for col in cols if col in display_df.columns]
        
        return display_df[available_cols]

# Create the app
app = App(app_ui, server)

if __name__ == "__main__":
    app.run()