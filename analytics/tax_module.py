import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import date, timedelta
import logging
from core.schema import TaxLot, HarvestOpportunity, TickerData

logger = logging.getLogger(__name__)

class TaxEngine:
    """
    Identifies tax-loss harvesting opportunities and suggests proxies
    to avoid Wash Sale violations.
    """
    
    def __init__(self, risk_model=None):
        self.risk_model = risk_model
        
    def check_wash_sale_rule(self, symbol: str, transaction_date: date, 
                             recent_transactions: List[Dict]) -> bool:
        """
        Checks if a sale would trigger a wash sale based on purchases 
        within +/- 30 days. 
        """
        # Simplified simulation: Look for any 'buy' of this symbol in last 30 days
        limit_date = transaction_date - timedelta(days=30)
        
        for txn in recent_transactions:
            if txn['symbol'] == symbol and txn['type'] == 'buy':
                txn_date = txn['date']
                if txn_date >= limit_date and txn_date <= transaction_date:
                    return True
        return False

    def find_proxy(self, loser_ticker: str, sector: str, 
                   candidate_tickers: List[TickerData],
                   correlation_matrix: Optional[pd.DataFrame] = None) -> str:
        """
        Finds a suitable proxy stock in the same sector.
        Ideally high correlation (to maintain tracking) but not "substantially identical".
        """
        # Filter for same sector
        sector_peers = [t.symbol for t in candidate_tickers if t.sector == sector and t.symbol != loser_ticker]
        
        if not sector_peers:
            return "SPY" # Fallback
            
        if correlation_matrix is not None and not correlation_matrix.empty:
            try:
                # Get correlations for the loser ticker
                if loser_ticker in correlation_matrix.index:
                    corrs = correlation_matrix[loser_ticker]
                    # Filter for sector peers
                    peer_corrs = corrs[corrs.index.isin(sector_peers)]
                    # Sort desc, pick top
                    if not peer_corrs.empty:
                        best_proxy = peer_corrs.idxmax()
                        logger.info(f"Found proxy for {loser_ticker} using correlation: {best_proxy} (corr: {peer_corrs.max():.2f})")
                        return best_proxy
            except Exception as e:
                logger.warning(f"Correlation lookup failed: {e}. Falling back to random peer.")
        
        # Fallback: Pick a random peer in the sector
        return sector_peers[0]

    def harvest_losses(self, portfolio_lots: List[TaxLot], 
                       market_prices: Dict[str, float],
                       candidate_tickers: List[TickerData],
                       correlation_matrix: Optional[pd.DataFrame] = None) -> List[HarvestOpportunity]:
        """
        Scans portfolio for lots with > 10% Unrealized Loss.
        """
        opportunities = []
        
        for lot in portfolio_lots:
            # Update current price if available
            if lot.symbol in market_prices:
                lot.current_price = market_prices[lot.symbol]
            
            # Check threshold (e.g. -10%)
            if lot.loss_percentage <= -0.10:
                # Find Proxy
                # Need to find the sector for this ticker from candidate_tickers
                ticker_obj = next((t for t in candidate_tickers if t.symbol == lot.symbol), None)
                sector = ticker_obj.sector if ticker_obj else "Unknown"
                
                proxy = self.find_proxy(lot.symbol, sector, candidate_tickers, correlation_matrix)
                
                opp = HarvestOpportunity(
                    sell_ticker=lot.symbol,
                    buy_proxy_ticker=proxy,
                    quantity=lot.quantity,
                    estimated_loss_harvested=abs(lot.unrealized_pl),
                    reason=f"Loss of {lot.loss_percentage*100:.1f}% exceeds 10% threshold."
                )
                opportunities.append(opp)
                
        logger.info(f"Identified {len(opportunities)} tax-loss harvesting opportunities.")
        return opportunities
