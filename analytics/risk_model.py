import pandas as pd
import numpy as np
from sklearn.covariance import LedoitWolf
import logging

logger = logging.getLogger(__name__)

class RiskModel:
    """
    Computes the covariance matrix of asset returns using Ledoit-Wolf Shrinkage.
    This is essential for high-dimensional portfolios (N > 500) where the 
    sample covariance matrix is often ill-conditioned or noisy.
    """
    
    def __init__(self):
        pass

    def compute_covariance_matrix(self, returns: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates the shrunk covariance matrix.
        
        Args:
            returns (pd.DataFrame): Historical daily returns (Date index, Ticker columns).
            
        Returns:
            pd.DataFrame: Covariance matrix (Ticker index, Ticker columns).
        """
        if returns.empty:
            logger.error("Returns dataframe is empty. Cannot compute covariance.")
            raise ValueError("Empty returns dataframe.")
            
        logger.info(f"Computing Ledoit-Wolf shrinkage covariance for {returns.shape[1]} assets...")
        
        # Use scikit-learn's LedoitWolf estimator
        lw = LedoitWolf()
        
        # Fit logic
        # Note: scikit-learn expects (n_samples, n_features). 
        # Our returns df is already (n_days, n_tickers), which matches.
        try:
            X = returns.values
            lw.fit(X)
            
            # The estimated covariance matrix
            cov_matrix = lw.covariance_
            
            # Reconstruct DataFrame
            cov_df = pd.DataFrame(
                cov_matrix, 
                index=returns.columns, 
                columns=returns.columns
            )
            logger.info("Covariance matrix computation successful.")
            return cov_df
            
        except Exception as e:
            logger.error(f"Failed to compute covariance matrix: {e}")
            raise e
