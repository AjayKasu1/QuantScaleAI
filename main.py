import logging
import pandas as pd
from typing import Dict, Any

from config import settings
from data.data_manager import MarketDataEngine
from analytics.risk_model import RiskModel
from data.optimizer import PortfolioOptimizer
from analytics.tax_module import TaxEngine
from analytics.attribution import AttributionEngine
from ai.ai_reporter import AIReporter
from core.schema import OptimizationRequest, TickerData

# Setup Logging
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("QuantScaleAI")

class QuantScaleSystem:
    def __init__(self):
        self.data_engine = MarketDataEngine()
        self.risk_model = RiskModel()
        self.optimizer = PortfolioOptimizer()
        self.tax_engine = TaxEngine()
        self.attribution_engine = AttributionEngine()
        self.ai_reporter = AIReporter()
        
    def run_pipeline(self, request: OptimizationRequest):
        logger.info(f"Starting pipeline for Client {request.client_id}...")
        
        # 1. Fetch Universe (S&P 500)
        tickers = self.data_engine.fetch_sp500_tickers()
        # Limit for demo speed if needed, but let's try full
        # tickers = tickers[:50] 
        
        # 2. Get Market Data
        # Fetch last 2 years for covariance
        data = self.data_engine.fetch_market_data(tickers, start_date="2023-01-01")
        if data.empty:
            logger.error("No market data available. Aborting.")
            return None
            
        returns = data.pct_change().dropna()
        
        # 3. Compute Risk Model
        # Ensure we align returns and tickers
        valid_tickers = returns.columns.tolist()
        cov_matrix = self.risk_model.compute_covariance_matrix(returns)
        
        # 4. Get Benchmark Data (S&P 500)
        # Fetch benchmark to calculate weights used for Tracking Error
        # Simplification: Assume Market Cap weights or Equal weights for the benchmark 
        # since getting live weights is hard without expensive data.
        # We will assume Equal Weights for the Benchmark in this demo logic 
        # or use a proxy. 
        # BETTER: Use SPY returns as the benchmark returns series for optimization.
        
        # For the optimizer, we need "Benchmark Weights" if we want to minimize active weight variance.
        # If we just map to S&P 500, let's assume valid_tickers ARE the index.
        # 4. Get Benchmark Data (S&P 500)
        # Fetch benchmark to calculate weights used for Tracking Error
        # REALISTIC PROXY: S&P 500 is Market Cap Weighted.
        # We manually assign Top 10 weights to make Tracking Error realistic when checking exclusions.
        
        n_assets = len(valid_tickers)
        benchmark_weights = pd.Series(0.0, index=valid_tickers)
        
        # Approximate weights (Feb 2026-ish Reality)
        # Total Market Cap heavily skewed to Mag 7
        top_weights = {
            "MSFT": 0.070, "AAPL": 0.065, "NVDA": 0.060, 
            "AMZN": 0.035, "GOOGL": 0.020, "GOOG": 0.020,
            "META": 0.020, "TSLA": 0.015, "BRK-B": 0.015,
            "LLY": 0.012, "AVGO": 0.012, "JPM": 0.010
        }
        
        current_total = 0.0
        for t, w in top_weights.items():
            if t in valid_tickers:
                benchmark_weights[t] = w
                current_total += w
                
        # Distribute remaining weight equally among rest
        remaining_weight = 1.0 - current_total
        remaining_count = n_assets - len([t for t in top_weights if t in valid_tickers])
        
        if remaining_count > 0:
            avg_rest = remaining_weight / remaining_count
            for t in valid_tickers:
                if benchmark_weights[t] == 0.0:
                    benchmark_weights[t] = avg_rest
                    
        # Normalize just in case
        benchmark_weights = benchmark_weights / benchmark_weights.sum()
        
        # 5. Optimize Portfolio
        sector_map = self.data_engine.get_sector_map()
        
        opt_result = self.optimizer.optimize_portfolio(
            covariance_matrix=cov_matrix,
            tickers=valid_tickers,
            benchmark_weights=benchmark_weights,
            sector_map=sector_map,
            excluded_sectors=request.excluded_sectors,
            excluded_tickers=request.excluded_tickers,
            max_weight=request.max_weight
        )
        
        if opt_result.status != "optimal":
            logger.warning("Optimization might be suboptimal.")
            
        # 6. Attribution Analysis (Simulated Performance)
        # We need "performance" loop.
        # Let's calculate return over the LAST MONTH for attribution
        last_month = returns.iloc[-21:]
        asset_period_return = (1 + last_month).prod() - 1
        
        attribution = self.attribution_engine.generate_attribution_report(
            portfolio_weights=opt_result.weights,
            benchmark_weights=benchmark_weights.to_dict(),
            asset_returns=asset_period_return,
            sector_map=sector_map
        )
        
        # 7. AI Reporting
        # Combine exclusions for the narrative
        exclusions_list = request.excluded_sectors + request.excluded_tickers
        excluded = ", ".join(exclusions_list) if exclusions_list else "None"
        
        commentary = self.ai_reporter.generate_report(attribution, excluded)
        
        return {
            "optimization": opt_result,
            "attribution": attribution,
            "commentary": commentary
        }

if __name__ == "__main__":
    # Test Run
    req = OptimizationRequest(
        client_id="TEST_001", 
        excluded_sectors=["Energy"] # Typical ESG constraint
    )
    system = QuantScaleSystem()
    result = system.run_pipeline(req)
    
    if result:
        print("\n--- AI COMMENTARY ---\n")
        print(result['commentary'])
