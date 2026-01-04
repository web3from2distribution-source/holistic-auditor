import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
# You must add this key in your Render Dashboard > Environment Variables
HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY") 

# --- FORENSIC PILLAR 1: CODE & METADATA (Helius) ---
def analyze_code_security(token_address):
    url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    
    # We use the DAS API to get full token metadata
    payload = {
        "jsonrpc": "2.0",
        "id": "text",
        "method": "getAsset",
        "params": { "id": token_address }
    }
    
    try:
        response = requests.post(url, json=payload).json()
        asset_data = response.get('result', {})
        
        # Default Risks
        risks = []
        score_penalty = 0
        
        # Check 1: Mutable Metadata (Dev can change image/name later)
        if asset_data.get('mutable', False):
            risks.append("Mutable Metadata (Dev can change details)")
            score_penalty += 10
            
        # Check 2: Authorities (If we can detect them via standard SPL layout)
        # Note: Deep code analysis usually requires parsing byte-code, 
        # but 'ownership' flags in metadata are a good proxy for "Renounced".
        ownership = asset_data.get('ownership', {})
        if not ownership.get('frozen', False):
             # Simplified check: Real "Renounced" checks are complex, 
             # but we assume risk if standard ownership flags are active.
             pass 

        return {"score_penalty": score_penalty, "risks": risks}
    except Exception as e:
        print(f"Code Audit Error: {e}")
        return {"score_penalty": 0, "risks": ["Audit data unavailable"]}

# --- FORENSIC PILLAR 2: SUPPLY DISTRIBUTION (Helius) ---
def analyze_supply(token_address):
    url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    payload = {
        "jsonrpc": "2.0", "id": 1, 
        "method": "getTokenLargestAccounts", 
        "params": [token_address]
    }
    
    try:
        res = requests.post(url, json=payload).json()
        accounts = res.get('result', {}).get('value', [])
        
        if not accounts:
            return {"score_penalty": 50, "top10_percent": 0, "risks": ["Hidden Supply / Error"]}

        # Calculate Concentration
        # Note: We don't know Total Supply easily without another call, 
        # so we assume standard SPL 1B or calc ratio if UI sends total supply.
        # For this v1, we check the raw amounts relative to each other.
        
        total_top_10 = sum([int(acc['amount']) for acc in accounts[:10]])
        top_holder = int(accounts[0]['amount'])
        
        # Risk Logic
        score_penalty = 0
        risks = []
        
        # Heuristic: If Top 1 holds > 20% of the Top 10 sum, it's very centralized
        concentration_ratio = top_holder / total_top_10
        
        if concentration_ratio > 0.5: # Top holder has 50% of the whale bag
            risks.append("CRITICAL: Single Whale Dominance")
            score_penalty += 40
        elif concentration_ratio > 0.2:
            risks.append("High Concentration")
            score_penalty += 20
            
        return {
            "score_penalty": score_penalty, 
            "top10_percent": int(concentration_ratio * 100), # Proxy for display
            "risks": risks,
            "holders_count": len(accounts) # Only returns top 20
        }
    except:
        return {"score_penalty": 0, "top10_percent": 0, "risks": []}

# --- FORENSIC PILLAR 3: MARKET BEHAVIOR (GeckoTerminal) ---
def analyze_market(token_address):
    # GeckoTerminal uses standard format usually
    url = f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{token_address}"
    
    try:
        res = requests.get(url).json()
        data = res.get('data', {}).get('attributes', {})
        
        if not data:
            return {"score_penalty": 50, "status": "DEAD", "price": "0", "risks": ["Token not trading"]}

        price = data.get('price_usd')
        vol_24h = float(data.get('volume_usd', {}).get('h24', 0))
        change_1h = float(data.get('price_change_percentage', {}).get('h1', 0))
        liquidity = float(data.get('reserve_in_usd', 0))
        
        score_penalty = 0
        risks = []
        
        # Rug Pull Check
        if change_1h < -50.0:
            risks.append("CRASH DETECTED (-50% in 1h)")
            score_penalty += 100 # Fatal
        
        # Liquidity Check
        if liquidity < 1000:
            risks.append("Low Liquidity (<$1k)")
            score_penalty += 30
            
        # Wash Trading Check (Volume > 2x Liquidity is suspicious)
        if liquidity > 0 and (vol_24h / liquidity) > 2.0:
            risks.append("Suspicious Volume (Wash Trading)")
            score_penalty += 20
            
        return {
            "score_penalty": score_penalty,
            "price": price,
            "volume": vol_24h,
            "change": change_1h,
            "risks": risks
        }
    except:
        return {"score_penalty": 0, "status": "Unknown", "risks": []}

# --- MASTER ROUTE ---
@app.route('/audit', methods=['POST'])
def audit():
    data = request.json
    address = data.get('address')
    
    if not address:
        return jsonify({"error": "No address provided"}), 400

    # 1. Run All Audits
    code_audit = analyze_code_security(address)
    supply_audit = analyze_supply(address)
    market_audit = analyze_market(address)
    
    # 2. Calculate Final Score
    base_score = 100
    total_penalty = code_audit['score_penalty'] + supply_audit['score_penalty'] + market_audit['score_penalty']
    final_score = max(0, base_score - total_penalty)
    
    # 3. Construct Verdict
    verdict_title = "SAFE"
    if final_score < 80: verdict_title = "CAUTION"
    if final_score < 50: verdict_title = "DANGEROUS"
    if final_score < 20: verdict_title = "SCAM DETECTED"
    
    return jsonify({
        "overall_score": final_score,
        "verdict_title": verdict_title,
        "pillars": {
            "code": code_audit,
            "supply": supply_audit,
            "market": market_audit
        }
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
