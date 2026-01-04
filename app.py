import os
import time
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# SECURITY 1: CORS Lock (Only allow your Netlify site)
# Replace 'https://your-site.netlify.app' with your ACTUAL Netlify URL after you deploy
CORS(app, resources={r"/audit": {"origins": "*"}}) 

# CONFIGURATION
HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY")
# YOUR WALLET ADDRESS (Must match the one in frontend)
TREASURY_WALLET = "YOUR_SOLANA_WALLET_ADDRESS_HERE" 
REQUIRED_AMOUNT_SOL = 0.002

# MEMORY CACHE (To prevent reusing the same payment signature)
used_signatures = set()

def verify_payment(signature):
    """
    Asks the Solana Blockchain: "Did this signature actually pay me 0.002 SOL?"
    """
    if not signature:
        return False, "No signature provided"
    
    if signature in used_signatures:
        return False, "Payment already used"

    url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
        ]
    }

    try:
        response = requests.post(url, json=payload).json()
        
        # 1. Check if transaction exists and is successful
        if 'error' in response or not response.get('result'):
            return False, "Transaction not found"
        
        tx_data = response['result']
        if tx_data['meta']['err']:
            return False, "Transaction failed on-chain"

        # 2. Check who received money (The Parsing Logic)
        # We look at preBalances and postBalances to calculate the change
        account_keys = [x['pubkey'] for x in tx_data['transaction']['message']['accountKeys']]
        
        # Find index of your Treasury Wallet
        try:
            treasury_index = account_keys.index(TREASURY_WALLET)
        except ValueError:
            return False, "Treasury wallet not involved in transaction"

        pre_balance = tx_data['meta']['preBalances'][treasury_index]
        post_balance = tx_data['meta']['postBalances'][treasury_index]
        
        received_lamports = post_balance - pre_balance
        received_sol = received_lamports / 1_000_000_000

        # 3. Validate Amount
        if received_sol >= (REQUIRED_AMOUNT_SOL - 0.000005): # Small buffer for dust
            used_signatures.add(signature) # Mark as used
            return True, "Payment Verified"
        else:
            return False, f"Insufficient payment. Received: {received_sol} SOL"

    except Exception as e:
        print(f"Payment Verification Error: {e}")
        return False, "Server Error during verification"

# --- THE SECURE ROUTE ---
@app.route('/audit', methods=['POST'])
def audit():
    data = request.json
    address = data.get('address')
    signature = data.get('signature') # <--- NEW REQUIREMENT

    # 1. VERIFY PAYMENT FIRST
    is_valid, message = verify_payment(signature)
    
    # If using 'SIMULATE' bypass (Only for your internal demos, remove in STRICT mode)
    if address and "SIMULATE" in address:
        pass # Allow demos without payment
    elif not is_valid:
        return jsonify({"error": message, "overall_score": 0}), 402 # 402 = Payment Required

    # 2. IF PAID, RUN AUDIT (The Logic from before)
    # ... [Paste the analyze_code/supply/market functions here from previous step] ...
    # For brevity, I am calling a dummy function here, but keep your real logic!
    return perform_audit_logic(address)

def perform_audit_logic(address):
    # ... (Keep your analyze_code, analyze_supply, analyze_market functions here) ...
    # This is just a placeholder to show where the logic goes
    return jsonify({
        "overall_score": 85,
        "verdict_title": "SECURE",
        "pillars": {
            "market": {"risks": [], "price": "1.20", "volume": "500K"},
            "supply": {"risks": [], "top10_percent": 15, "holders_count": 1200},
            "code": {"risks": [], "score_penalty": 0}
        }
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
    
