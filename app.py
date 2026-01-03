import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
HELIUS_KEY = os.environ.get("HELIUS_API_KEY")

# --- PILLAR 3: GECKOTERMINAL (The Crash Detector) ---
def check_price_crash(token_address):
    # We use GeckoTerminal because it sees NEW tokens on Solana instantly
    network = "solana"
    url = f"https://api.geckoterminal.com/api/v2/networks/{network}/tokens/{token_address}"
    
    try:
        response = requests.get(url).json()
        
        # 1. Extract Data
        attributes = response['data']['attributes']
        price_usd = attributes.get('price_usd')
        price_change_1h = attributes['price_change_percentage'].get('h1')
        volume_24h = attributes.get('volume_usd')['h24']
        
        report = {
            "price": price_usd,
            "1h_change": f"{price_change_1h}%",
            "volume": volume_24h,
            "status": "Stable"
        }

        # 2. THE RUG PULL LOGIC (Crash Detection)
        # If price dropped more than 50% in 1 hour, it's a crash.
        if float(price_change_1h) < -50.0:
            report["status"] = "CRASH DETECTED (Rug Pull)"
            report["risk_score"] = 0 # Fatal
        
        # 3. THE FAKE VOLUME LOGIC
        # If volume is huge ($1M+) but price didn't move, it's wash trading.
        elif float(volume_24h) > 1000000 and abs(float(price_change_1h)) < 1.0:
            report["status"] = "Suspicious: Fake Volume Detected"
        
        return report

    except Exception as e:
        return {"error": "Token not trading yet or API Error", "details": str(e)}

# --- PILLAR 2: HELIUS (The Bundle Detector) ---
def check_holders(token_address):
    # (Same Helius logic as before)
    url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
    payload = {
        "jsonrpc": "2.0", "id": 1, 
        "method": "getTokenLargestAccounts", 
        "params": [token_address]
    }
    try:
        res = requests.post(url, json=payload).json()
        if 'error' in res: return []
        holders = [x['address'] for x in res['result']['value'][:20]]
        return holders
    except:
        return []

# --- THE MASTER BRAIN ---
@app.route('/audit', methods=['POST'])
def holistic_audit():
    data = request.json
    address = data.get('address')
    
    # Initialize the Report Card
    full_report = {
        "overall_score": 100,
        "pillars": {}
    }

    # 1. Run The Crash Detector (GeckoTerminal)
    market_data = check_price_crash(address)
    full_report["pillars"]["behavior"] = market_data

    # Penalty Check
    if "CRASH" in market_data.get("status", ""):
        full_report["overall_score"] = 0 # Instant Fail

    # 2. Run The Bundle Detector (Helius)
    holders = check_holders(address)
    if len(holders) > 0 and len(holders) < 10:
        full_report["pillars"]["distribution"] = {"risk": "High: < 10 Holders detected"}
        full_report["overall_score"] -= 50
    else:
        full_report["pillars"]["distribution"] = {"status": "Pass", "holder_count": len(holders)}

    return jsonify(full_report)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
    
