"""
FSI Transaction Simulator
Generates synthetic raw transactions and inserts into TRANSACTION_STAGING table.
"""

import os
import time
import random
from datetime import datetime, timedelta
from snowflake.snowpark import Session


def get_session():
    """Get Snowflake session with automatic fallback"""
    sf_home = os.getenv("SNOWFLAKE_HOME", "")
    
    # Try workbench connection first
    if sf_home:
        try:
            session = Session.builder.configs({
                "connection_name": "workbench",
                "database": "FSI_DEMO",
                "schema": "RAW_BANKING",
            }).create()
            print("[auth] ✓ Connected via workbench")
            return session
        except Exception as e:
            print(f"[auth] Workbench connection failed: {e}")
    
    # Fallback to OAuth token
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
            print("[auth] ✓ Connected via OAuth token")
            return session
        except Exception as e:
            print(f"[auth] OAuth token connection failed: {e}")
            print("[auth] Token may be expired. Please refresh SNOWFLAKE_TOKEN.")
    
    raise RuntimeError(
        "Could not connect to Snowflake.\n"
        "Set SNOWFLAKE_TOKEN environment variable with a fresh OAuth token.\n"
        "Or ensure SNOWFLAKE_HOME is set for workbench connection."
    )


class SessionPool:
    def __init__(self):
        self.session = None
        self.last_refresh = None
        self.refresh_interval = timedelta(minutes=25)
    
    def get_session(self):
        """Get session, refresh if needed"""
        now = datetime.now()
        
        if (self.session is None or 
            self.last_refresh is None or 
            now - self.last_refresh > self.refresh_interval):
            
            if self.session:
                try:
                    self.session.close()
                    print(f"[pool] Closed old session at {now.strftime('%H:%M:%S')}")
                except:
                    pass
            
            print(f"[pool] Creating new session at {now.strftime('%H:%M:%S')}")
            self.session = get_session()
            self.last_refresh = now
        
        return self.session


# Create global session pool
session_pool = SessionPool()


CHANNELS = ["Online Banking", "Mobile App", "ATM", "Branch", "Point of Sale"]
TYPES = ["DEBIT", "CREDIT", "TRANSFER", "WITHDRAWAL", "DEPOSIT", "PAYMENT"]
MERCHANTS = [
    ("Amazon", "5411"), ("Walmart", "5411"), ("Target", "5311"),
    ("Costco", "5300"), ("Best Buy", "5732"), ("Starbucks", "5814"),
    ("Shell Gas", "5541"), ("Whole Foods", "5411"), ("CVS", "5912"),
    ("Home Depot", "5200"), ("Uber", "4121"), ("Netflix", "4899"),
    ("Chipotle", "5812"), ("Delta Airlines", "3058"), ("Marriott", "7011"),
]
DESCRIPTIONS = {
    "DEBIT": ["Purchase", "POS Transaction", "Card Payment"],
    "CREDIT": ["Refund", "Cashback Reward", "Credit Adjustment"],
    "TRANSFER": ["Wire Transfer", "ACH Transfer", "Internal Transfer"],
    "WITHDRAWAL": ["ATM Withdrawal", "Cash Advance", "Counter Withdrawal"],
    "DEPOSIT": ["Direct Deposit", "Mobile Deposit", "Branch Deposit"],
    "PAYMENT": ["Bill Payment", "Loan Payment", "Insurance Payment"],
}


# Simplified INSERT for raw transactions only
INSERT_SQL = """
INSERT INTO FSI_DEMO.RAW_BANKING.TRANSACTION_STAGING (
    TRANSACTION_ID, ACCOUNT_NUMBER, TRANSACTION_POST_DATE,
    TRANSACTION_TIMESTAMP, TRANSACTION_TYPE, TRANSACTION_DESCRIPTION,
    TRANSACTION_AMOUNT, CHANNEL_NAME, MERCHANT_NAME,
    MERCHANT_CATEGORY_CODE, IS_INTERNATIONAL, REVERSAL_FLAG,
    RECORD_CREATED_TS
) VALUES (
    '{txn_id}', '{acct}', '{post_date}',
    '{ts}', '{txn_type}', '{descr}',
    {amount}, '{channel}', '{merchant}',
    '{mcc}', {intl}, {reversal},
    CURRENT_TIMESTAMP()
)
"""


def generate_and_insert(session):
    acct_num = f"AC{random.randint(1, 4000):010d}"
    txn_type = random.choice(TYPES)
    merchant_name, mcc = random.choice(MERCHANTS)
    is_international = random.random() < 0.05
    channel = random.choice(CHANNELS)

    # Generate transaction amount
    if random.random() < 0.90:
        amount = round(random.lognormvariate(4, 1.5), 2)
    else:
        amount = round(random.uniform(1000, 10000), 2)
    amount = min(amount, 99999.99)

    # Generate timestamp
    now = datetime.utcnow()
    ts = now - timedelta(seconds=random.randint(0, 300))
    
    # Format timestamp properly for Snowflake
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
    
    # Generate transaction ID and description
    txn_id = f"TXN{int(time.time() * 1000)}{random.randint(1000, 9999)}"
    descr = random.choice(DESCRIPTIONS[txn_type]) + " - " + merchant_name

    sql = INSERT_SQL.format(
        txn_id=txn_id,
        acct=acct_num,
        post_date=ts.strftime("%Y-%m-%d"),
        ts=ts_str,
        txn_type=txn_type,
        descr=descr.replace("'", "''"),
        amount=amount,
        channel=channel,
        merchant=merchant_name.replace("'", "''"),
        mcc=mcc,
        intl="TRUE" if is_international else "FALSE",
        reversal="TRUE" if random.random() < 0.02 else "FALSE",
    )
    session.sql(sql).collect()

    return {
        "txn_id": txn_id,
        "amount": amount,
        "channel": channel,
        "txn_type": txn_type,
        "is_international": is_international,
    }


def run_simulator(batch_size=3, interval=10, duration=None):
    print("=" * 70)
    print("  FSI TRANSACTION SIMULATOR - AmeriFirst Banking")
    print("=" * 70)
    print(f"  Batch size : {batch_size} txns every {interval}s")
    print(f"  Duration   : {duration or 'infinite'}s")
    print(f"  Target     : FSI_DEMO.RAW_BANKING.TRANSACTION_STAGING")
    print("=" * 70)

    session = session_pool.get_session()
    
    print(f"[ok] Connected as {session.sql('SELECT CURRENT_USER()').collect()[0][0]}")
    print(f"[ok] Warehouse: {session.sql('SELECT CURRENT_WAREHOUSE()').collect()[0][0]}\n")

    start = time.time()
    total = 0

    try:
        while True:
            if duration and (time.time() - start) > duration:
                print("\nDuration limit reached.")
                break

            session = session_pool.get_session()

            for _ in range(batch_size):
                try:
                    txn = generate_and_insert(session)
                    total += 1
                    flag = ""
                    if txn["is_international"] and txn["amount"] > 3000:
                        flag = " 🌍 INTL"
                    
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"#{total:>5d}  {txn['txn_id']}  "
                        f"${txn['amount']:>9,.2f}  "
                        f"{txn['channel']:<18s}  "
                        f"{txn['txn_type']:<12s}"
                        f"{flag}"
                    )
                except Exception as e:
                    print(f"[ERROR] Failed to insert transaction: {e}")
                    session_pool.session = None
                    session = session_pool.get_session()

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    finally:
        if session_pool.session:
            session_pool.session.close()
        elapsed = time.time() - start
        print(f"\nTotal inserted: {total}  |  Elapsed: {elapsed:.0f}s  |  Rate: {total / max(elapsed, 1):.2f} txn/s")


if __name__ == "__main__":
    run_simulator(
        batch_size=int(os.getenv("BATCH_SIZE", "3")),
        interval=int(os.getenv("INTERVAL", "10")),
        duration=int(os.getenv("DURATION", "0")) or None,
    )