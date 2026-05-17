"""
Fraud Scoring Scheduler
Calls the fraud scoring API endpoint when executed
"""
import requests
import os
from datetime import datetime

def main():
    """Main function that triggers fraud scoring"""
    # Get the API URL from environment variable
    api_url = os.getenv("SCORING_API_URL", "https://connect/content/YOUR_CONTENT_GUID/score")
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting fraud scoring trigger...")
    print(f"API URL: {api_url}")
    
    try:
        # Call the scoring API
        response = requests.post(api_url, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            transactions_scored = result.get('transactions_scored', 0)
            status = result.get('status', 'unknown')
            
            print(f"✓ SUCCESS: Scored {transactions_scored} transactions")
            print(f"  Status: {status}")
            
            # Return success message
            return {
                "success": True,
                "transactions_scored": transactions_scored,
                "status": status,
                "timestamp": datetime.now().isoformat()
            }
        else:
            error_msg = f"API returned status code {response.status_code}"
            print(f"✗ ERROR: {error_msg}")
            print(f"  Response: {response.text}")
            
            return {
                "success": False,
                "error": error_msg,
                "response": response.text,
                "timestamp": datetime.now().isoformat()
            }
            
    except requests.exceptions.Timeout:
        error_msg = "Request timed out after 5 minutes"
        print(f"✗ ERROR: {error_msg}")
        return {"success": False, "error": error_msg}
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"✗ ERROR: {error_msg}")
        return {"success": False, "error": error_msg}

if __name__ == "__main__":
    result = main()
    print(f"\nFinal result: {result}")
    
    # Exit with appropriate code
    if result.get("success"):
        exit(0)
    else:
        exit(1)
