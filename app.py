import os
import requests
import networkx as nx
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- API KEYS ---
HELIUS_KEY = os.environ.get("HELIUS_API_KEY")
CG_URL = "https://api.coingecko.com/api/v3"

# --- PILLAR 1: COINGECKO (Behavior & Price) ---
def check_market_data(token_address):
    # Note: Real CoinGecko requires the CoinID (e.g., 'solana'), not address for free tier usually.
    # We use a mock check here or platform specific endpoint if available.
    try:
        # Example: Fetching Solana price to compare liquidity depth
        url = f"{CG_URL}/simple/price?ids=solana&vs_currencies=usd&include_24hr_vol=true"
        data = requests.get(url).json()
        return {"price_data": data, "status": "Active"}
    except:
        return {"error": "CoinGecko Data Unavailable"}

# --- PILLAR 2: HELIUS (Holders & Clusters) ---
def check_holders(token_address):
    url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
    payload = {
        "jsonrpc": "2.0", "id": 1, 
        "method": "getTokenLargestAccounts", 
        "params": [token_address]
    }
    try:
        res = requests.post(url, json=payload).json()
        holders = [x['address'] for x in res['result']['value'][:20]]
        return holders
    except:
        return []

# --- THE MASTER ROUTE ---
@app.route('/audit', methods=['POST'])
def holistic_audit():
    data = request.json
    address = data.get('address')
    
    report = {
        "score": 100,
        "pillars": {
            "code": "Pending Slither Scan...", # Requires Async worker
            "distribution": {},
            "behavior": {}
        }
    }

    # 1. Run CoinGecko Check
    cg_data = check_market_data(address)
    report["pillars"]["behavior"] = cg_data

    # 2. Run Helius Check (Bundling)
    holders = check_holders(address)
    if len(holders) < 5:
        report["score"] -= 50
        report["pillars"]["distribution"] = {"risk": "CRITICAL: Low Holder Count"}
    else:
        report["pillars"]["distribution"] = {"status": "Analysis Complete", "top_holders": len(holders)}

    return jsonify(report)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
