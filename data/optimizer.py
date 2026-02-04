import cvxpy as cp
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Optional
from core.schema import OptimizationResult
from config import settings

logger = logging.getLogger(__name__)

class PortfolioOptimizer:
    """
    Quantitative Optimization Engine using CVXPY.
    Objective: Minimize Tracking Error against a Benchmark.
    Constraints: 
    1. Full Investment (Sum w = 1)
    2. Long Only (w >= 0)
    3. Sector Exclusions (w[excluded] = 0)
    """
    
    def __init__(self):
        pass

    def optimize_portfolio(self, 
                           covariance_matrix: pd.DataFrame,
                           tickers: List[str],
                           benchmark_weights: pd.DataFrame,
                           sector_map: Dict[str, str],
                           excluded_sectors: List[str],
                           excluded_tickers: List[str] = None) -> OptimizationResult:
        """
        Solves the tracking error minimization problem.
        
        Args:
            covariance_matrix: (N x N) Ledoit-Wolf shrunk covariance matrix.
            tickers: List of N tickers.
            benchmark_weights: (N x 1) Weights of the benchmark (e.g. S&P 500). 
                               Un-held assets should have 0 weight.
            sector_map: Dictionary mapping ticker -> sector.
            excluded_sectors: List of sectors to exclude.
            excluded_tickers: List of specific tickers to exclude.
            
        Returns:
            OptimizationResult containing weights and status.
        """
        excluded_tickers = excluded_tickers or []
        n_assets = len(tickers)
        if covariance_matrix.shape != (n_assets, n_assets):
            raise ValueError(f"Covariance matrix shape {covariance_matrix.shape} does not match tickers count {n_assets}")

        logger.info(f"Setting up CVXPY optimization for {n_assets} assets...")

        # Variables
        w = cp.Variable(n_assets)
        
        # Benchmark Weights Vector (aligned to tickers)
        if isinstance(benchmark_weights, (pd.Series, pd.DataFrame)):
            w_b = benchmark_weights.reindex(tickers).fillna(0).values.flatten()
        else:
            w_b = np.array(benchmark_weights)

        # Objective
        active_weights = w - w_b
        tracking_error_variance = cp.quad_form(active_weights, covariance_matrix.values)
        objective = cp.Minimize(tracking_error_variance)
        
        # 1. Identify Exclusions FIRST to adjust constraints
        excluded_indices = []
        mask_vector = np.zeros(n_assets)
        
        # Sector Exclusions
        if excluded_sectors:
            logger.info(f"Applying Sector Exclusion Validation for: {excluded_sectors}")
            for i, ticker in enumerate(tickers):
                sector = sector_map.get(ticker, "Unknown")
                for excl in excluded_sectors:
                     if excl.lower() == sector.lower() or (excl == "Technology" and sector == "Information Technology"):
                        excluded_indices.append(i)
                        mask_vector[i] = 1

        # Ticker Exclusions (NEW)
        if excluded_tickers:
            logger.info(f"Applying Ticker Exclusion Validation for: {excluded_tickers}")
            for i, ticker in enumerate(tickers):
                 if ticker in excluded_tickers:
                    excluded_indices.append(i)
                    mask_vector[i] = 1
                    
        excluded_indices = list(set(excluded_indices)) # Dedupe
            
        logger.info(f"DEBUG: Excluded Mask Sum = {mask_vector.sum()} assets out of {n_assets}")
        
        if len(excluded_indices) == n_assets:
            raise ValueError("All assets excluded! Cannot optimize.")

        # 2. Dynamic Constraints
        n_active = n_assets - len(excluded_indices)
        if n_active == 0: n_active = 1
        
        min_avg_weight = 1.0 / n_active
        dynamic_max = max(0.20, min_avg_weight * 1.5)
        
        MAX_WEIGHT_LIMIT = dynamic_max
        logger.info(f"DEBUG: Active Assets={n_active}, Min Avg={min_avg_weight:.4f}, Dynamic Max Limit={MAX_WEIGHT_LIMIT:.4f}")
        
        constraints = [
            cp.sum(w) == 1,
            w >= 0,
            w <= MAX_WEIGHT_LIMIT
        ]
        
        # Apply Exclusions
        if excluded_indices:
             constraints.append(w[excluded_indices] == 0)

        # Problem
        prob = cp.Problem(objective, constraints)
        
        try:
            logger.info("Solving quadratic programming problem...")
            # verbose=True to see solver output in logs
            prob.solve(verbose=True) 
        except Exception as e:
            logger.error(f"Optimization CRASHED: {e}")
            raise e

        # CHECK SOLVER STATUS
        if prob.status not in [cp.OPTIMAL, cp.OPTIMAL_INACCURATE]:
            logger.error(f"Optimization FAILED with status: {prob.status}")
            raise ValueError(f"Solver failed: {prob.status}")

        # Extract weights
        optimal_weights = w.value
        if optimal_weights is None:
             raise ValueError("Solver returned None for weights.")
             
        # Add small tolerance cleanup
        optimal_weights[optimal_weights < 1e-4] = 0
        
        # Normalize just in case (solver precision)
        # optimal_weights = optimal_weights / optimal_weights.sum() 
        
        # Format Result
        weight_dict = {
            tickers[i]: float(optimal_weights[i]) 
            for i in range(n_assets) 
            if optimal_weights[i] > 0
        }
        
        # Calculate resulting Tracking Error (volatility of active returns)
        # TE = sqrt(variance)
        te = np.sqrt(prob.value) if prob.value > 0 else 0.0
        
        logger.info(f"Optimization Solved. Tracking Error: {te:.4f}")
        
        return OptimizationResult(
            weights=weight_dict,
            tracking_error=te,
            status=prob.status
        )
