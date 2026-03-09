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
        
        # 0. LLM Intent Parsing (New)
        if request.user_prompt and not request.excluded_sectors:
            logger.info(f"Parsing user intent: '{request.user_prompt}'")
            request.excluded_sectors = self.ai_reporter.parse_intent(request.user_prompt)
            logger.info(f"LLM Mapped Exclusions: {request.excluded_sectors}")

        # 1. Fetch Universe (S&P 500)
        tickers = self.data_engine.fetch_sp500_tickers()

        # OPTIMIZATION: Filter Universe BEFORE Fetching Data
        # But we MUST fetch "Market Drivers" to define a realistic Benchmark
        # Otherwise TE is 0.0 because Benchmark == Portfolio Universe
        
        caps = self.data_engine.fetch_market_caps(tickers)
        valid_caps = {t: c for t, c in caps.items() if c > 0}
        sorted_by_cap = sorted(valid_caps.keys(), key=lambda t: valid_caps[t])
        
        # Define "Market Drivers" (Top 20) - Essential for S&P 500 Proxy
        market_drivers = sorted_by_cap[-20:]
        
        valid_tickers_for_fetch = []
        
        if request.strategy and request.top_n:
            logger.info(f"Applying Strategy PRE-FETCH: {request.strategy} with Top N={request.top_n}")
            
            if request.strategy == "smallest_market_cap":
                targets = sorted_by_cap[:request.top_n]
                # We fetch Targets + Drivers
                valid_tickers_for_fetch = list(set(targets + market_drivers))
                logger.info(f"Fetching {len(valid_tickers_for_fetch)} tickers (Targets + Drivers)")
                
            elif request.strategy == "largest_market_cap":
                targets = sorted_by_cap[-request.top_n:]
                valid_tickers_for_fetch = list(set(targets + market_drivers))
        else:
             # Default safety limit for Demo
             valid_tickers_for_fetch = tickers[:60]

        # 2. Get Market Data (Only for filtered subset)
        # Fetch last 2 years for covariance
        data = self.data_engine.fetch_market_data(valid_tickers_for_fetch, start_date="2023-01-01")
        if data.empty:
            logger.error("No market data available. Aborting.")
            return None
            
        returns = data.pct_change().dropna()
        
        # 3. Compute Risk Model
        # Ensure we align returns and tickers
        valid_tickers = returns.columns.tolist()
        
        # Re-verify filter (data fetch might have dropped some)
        if request.strategy and request.top_n:
            # Re-sort based on what we actually have?
            # Or just proceed, since we pre-filtered.
            pass
            
        cov_matrix = self.risk_model.compute_covariance_matrix(returns)
        
        # 4. Get Benchmark Data (Realistic S&P 500 Proxy)
        # We assume the Driver stocks carry their heavy weight, and the rest is distributed
        
        n_assets = len(valid_tickers)
        benchmark_weights = pd.Series(0.0, index=valid_tickers)
        
        # Assign distinct weights to known Drivers if they are in our data
        # Approximate Mag 7 weights (or use market cap ratio if we had total cap)
        # Using a proxy distribution logic:
        
        # Calculate Total Cap of our universe subset to see relative sizing
        subset_caps = {t: valid_caps.get(t, 1e9) for t in valid_tickers}
        total_subset_cap = sum(subset_caps.values())
        
        # If we are missing 400 stocks, we can't normalize to 1.0 perfectly *relative to SPX*
        # But for the Optimizer's math (Port vs Bench), both must sum to 1.0 within the optimization universe?
        # NO. If we want TE against full SPX, we need to handle the "missing" variance. 
        # But simpler: Normalize weights within the Available Universe based on Cap.
        
        # For "Smallest 50" strategy:
        # The Drivers (AAPL, etc.) are in `valid_tickers` now.
        # So Benchmark will be Cap Weighted (90% Drivers, 10% Small Caps).
        # Portfolio will be Constrained to 0% Drivers.
        # Result -> Huge TE. Correct.
        
        for t in valid_tickers:
            benchmark_weights[t] = subset_caps[t] / total_subset_cap
            
        # 5. Optimize Portfolio
        sector_map = self.data_engine.get_sector_map()
        
        # If Strategy requires excluding the "Drivers" (because they aren't in the Target set)
        # We must add them to 'excluded_tickers' for the Optimizer
        
        final_exclusions = list(request.excluded_tickers)
        
        if request.strategy == "smallest_market_cap":
            # Exclude anything that IS NOT in the target list (i.e. exclude the Drivers)
            # targets from above
            targets = sorted_by_cap[:request.top_n]
            for t in valid_tickers:
                if t not in targets:
                    final_exclusions.append(t)
                    
        # ... logic for largest ...
        if request.strategy == "largest_market_cap":
             # Drivers are likely IN the target set, so no extra exclusion needed usually
             pass

        opt_result = self.optimizer.optimize_portfolio(
            covariance_matrix=cov_matrix,
            tickers=valid_tickers,
            benchmark_weights=benchmark_weights,
            sector_map=sector_map,
            excluded_sectors=request.excluded_sectors,
            excluded_tickers=final_exclusions,
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
        
        commentary = self.ai_reporter.generate_report(
            attribution_report=attribution, 
            excluded_sector=excluded,
            tracking_error=opt_result.tracking_error
        )
        
        return {
            "optimization": opt_result,
            "attribution": attribution,
            "commentary": commentary,
            "market_data": returns,
            "benchmark_weights": benchmark_weights,
            "sector_map": sector_map
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
# Force HF Build
