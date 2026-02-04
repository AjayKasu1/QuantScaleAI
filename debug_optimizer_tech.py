import pandas as pd
import numpy as np
import logging
from data.optimizer import PortfolioOptimizer
from core.schema import OptimizationResult

# Config Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_optimizer_exclusion():
    print("\n--- STARTING OPTIMIZER DEBUG TEST ---\n")
    
    # 1. Mock Data Setup (Mini S&P 500)
    tickers = ["AAPL", "MSFT", "GOOGL", "XOM", "CVX", "JPM", "BAC", "JNJ", "PFE", "NEE"]
    n = len(tickers)
    
    # Sector Map (Tech, Energy, Financials, Healthcare, Utilities)
    sector_map = {
        "AAPL": "Information Technology",
        "MSFT": "Information Technology", 
        "GOOGL": "Communication Services", # Often grouped with Tech
        "XOM": "Energy",
        "CVX": "Energy",
        "JPM": "Financials",
        "BAC": "Financials",
        "JNJ": "Health Care",
        "PFE": "Health Care",
        "NEE": "Utilities"
    }
    
    # Mock Covariance (Identity for simplicity, slight correlation)
    np.random.seed(42)
    cov_data = np.eye(n) * 0.0004 # Low variance
    cov_df = pd.DataFrame(cov_data, index=tickers, columns=tickers)
    
    # Benchmark weights (Equal weight benchmark for test)
    bench_weights = pd.Series(np.ones(n)/n, index=tickers)
    
    # 2. Instantiate Optimizer
    opt = PortfolioOptimizer()
    
    # 3. Test Cases
    
    # Case A: Normal
    print("\n[Case A] No Exclusions")
    res_a = opt.optimize_portfolio(cov_df, tickers, bench_weights, sector_map, [])
    print(f"Status: {res_a.status}, TE: {res_a.tracking_error:.4f}")
    
    # Case B: Exclude Energy (2 stocks)
    print("\n[Case B] Exclude Energy")
    res_b = opt.optimize_portfolio(cov_df, tickers, bench_weights, sector_map, ["Energy"])
    print(f"Status: {res_b.status}, TE: {res_b.tracking_error:.4f}")
    print(f"Weights: {res_b.weights}")
    assert "XOM" not in res_b.weights
    assert "CVX" not in res_b.weights
    
    # Case C: Exclude Tech (Heavyweights AAPL, MSFT) -> This usually breaks tight constraints!
    print("\n[Case C] Exclude Technology (The Failure Case)")
    try:
        # Note: sector_map uses "Information Technology", so we pass "Technology" and ensure the loop handles it
        # Or we act like the frontend and pass the mapped name?
        # The frontend usually sends "Technology". 
        # But wait, my optimizer code line 91 checks: if excl == sector or ...
        # My fixed code handles "Technology" == "Information Technology".
        
        # Let's pass "Technology"
        res_c = opt.optimize_portfolio(cov_df, tickers, bench_weights, sector_map, ["Technology"])
        print(f"Status: {res_c.status}, TE: {res_c.tracking_error:.4f}")
        print(f"Weights: {res_c.weights}")
        
        # Verification
        if "AAPL" in res_c.weights or "MSFT" in res_c.weights:
            print("❌ FAILURE: Tech stocks still in portfolio!")
        else:
            print("✅ SUCCESS: Tech stocks removed!")
            
    except Exception as e:
        print(f"❌ CRASHED: {e}")

if __name__ == "__main__":
    test_optimizer_exclusion()
