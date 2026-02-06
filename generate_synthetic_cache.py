import json
import random

def generate_synthetic_cache():
    # Load Universe
    with open('data/sp500_universe.json', 'r') as f:
        universe = json.load(f)
        
    caps = {}
    
    # Known Mega Caps (approx Trillions)
    mega_caps = {
        "AAPL": 3.4e12, "MSFT": 3.1e12, "NVDA": 2.8e12, "GOOGL": 2.1e12, "GOOG": 2.1e12,
        "AMZN": 1.9e12, "META": 1.2e12, "BRK-B": 900e9, "LLY": 800e9, "TSLA": 700e9,
        "AVGO": 650e9, "JPM": 600e9, "V": 550e9, "XOM": 500e9, "WMT": 500e9
    }
    
    for item in universe:
        t = item['ticker']
        if t in mega_caps:
            caps[t] = mega_caps[t]
        else:
            # Random distribution for the rest: 10B to 400B
            # Generating a "Long Tail" distribution
            # 80% are between 10B and 100B (Small/Mid)
            # 20% are between 100B and 400B (Large)
            if random.random() < 0.8:
                caps[t] = random.uniform(10e9, 100e9)
            else:
                caps[t] = random.uniform(100e9, 400e9)
                
    with open('data/market_cap_cache.json', 'w') as f:
        json.dump(caps, f, indent=2)
        
    print(f"Generated synthetic caps for {len(caps)} tickers.")

if __name__ == "__main__":
    generate_synthetic_cache()
