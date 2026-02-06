import yfinance as yf
import json
import concurrent.futures
import os
from data.data_manager import MarketDataEngine

def generate_cache():
    engine = MarketDataEngine()
    tickers = engine.fetch_sp500_tickers()
    print(f"Fetching caps for {len(tickers)} tickers...")
    
    caps = {}
    def get_cap(t):
        try:
            return t, yf.Ticker(t).fast_info['market_cap']
        except:
            return t, 0
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(get_cap, tickers)
        
    for t, c in results:
        if c > 0:
            caps[t] = c
            
    with open('data/market_cap_cache.json', 'w') as f:
        json.dump(caps, f, indent=2)
    print(f"Saved {len(caps)} caps to data/market_cap_cache.json")

if __name__ == "__main__":
    generate_cache()
