import pandas as pd
import numpy as np
from typing import Dict, List
import logging
from core.schema import AttributionReport

logger = logging.getLogger(__name__)

class AttributionEngine:
    """
    Implements the Brinson-Fachler Attribution Model.
    Decomposes portfolio excess return into:
    1. Allocation Effect: Value added by sector weighting decisions.
    2. Selection Effect: Value added by stock picking within sectors.
    """
    
    def __init__(self):
        pass
        
    def generate_attribution_report(self, 
                                    portfolio_weights: Dict[str, float], 
                                    benchmark_weights: Dict[str, float],
                                    asset_returns: pd.Series,
                                    sector_map: Dict[str, str]) -> AttributionReport:
        """
        Calculates attribution effects.
        
        Args:
            portfolio_weights: Ticker -> Weight
            benchmark_weights: Ticker -> Weight
            asset_returns: Ticker -> Return (period)
            sector_map: Ticker -> Sector
            
        Returns:
            AttributionReport object
        """
        # Create a DataFrame for calculation
        all_tickers = set(portfolio_weights.keys()) | set(benchmark_weights.keys())
        df = pd.DataFrame(index=list(all_tickers))
        
        df['wp'] = df.index.map(portfolio_weights).fillna(0.0)
        df['wb'] = df.index.map(benchmark_weights).fillna(0.0)
        df['ret'] = df.index.map(asset_returns).fillna(0.0)
        df['sector'] = df.index.map(sector_map).fillna("Unknown")
        
        # Calculate Sector Level Data
        # Sector Portfolio Return (R_pi), Sector Benchmark Return (R_bi)
        # Sector Portfolio Weight (w_pi), Sector Benchmark Weight (w_bi)
        
        sector_groups = df.groupby('sector')
        
        attribution_rows = []
        
        total_benchmark_return = (df['wb'] * df['ret']).sum()
        
        for sector, data in sector_groups:
            w_p = data['wp'].sum()
            w_b = data['wb'].sum()
            
            # Avoid division by zero if weight is 0
            R_p = (data['wp'] * data['ret']).sum() / w_p if w_p > 0 else 0
            R_b = (data['wb'] * data['ret']).sum() / w_b if w_b > 0 else 0
            
            # Brinson-Fachler Allocation: (w_p - w_b) * (R_b - R_total_benchmark)
            allocation_effect = (w_p - w_b) * (R_b - total_benchmark_return)
            
            # Selection Effect: w_b * (R_p - R_b)
            # Note: Often interaction is w_p * ... or split. 
            # Brinson-Beebower uses w_b for selection.
            selection_effect = w_b * (R_p - R_b)
            
            # Interaction: (w_p - w_b) * (R_p - R_b)
            interaction_effect = (w_p - w_b) * (R_p - R_b)
            
            attribution_rows.append({
                'sector': sector,
                'allocation': allocation_effect,
                'selection': selection_effect,
                'interaction': interaction_effect,
                'total_effect': allocation_effect + selection_effect + interaction_effect
            })
            
        attr_df = pd.DataFrame(attribution_rows)
        
        total_allocation = attr_df['allocation'].sum()
        total_selection = attr_df['selection'].sum() # + interaction usually bundled
        total_interaction = attr_df['interaction'].sum()
        
        # Calculate Top Contributors/Detractors to active return
        # Active Weight * Asset Return? Or Contribution to Active Return?
        # Contribution to Active Return = w_p*r_a - w_b*r_a ...
        df['active_weight'] = df['wp'] - df['wb']
        df['contribution'] = df['active_weight'] * df['ret'] # Simple approx
        
        sorted_contrib = df.sort_values(by='contribution', ascending=False)
        top_contributors = sorted_contrib.head(5).index.tolist()
        top_detractors = sorted_contrib.tail(5).index.tolist()
        
        # Narrative skeleton (to be filled by AI)
        narrative_raw = (
            f"Total Active Return: {(total_allocation + total_selection + total_interaction):.4f}. "
            f"Allocation Effect: {total_allocation:.4f}. "
            f"Selection Effect: {total_selection + total_interaction:.4f}."
        )

        return AttributionReport(
            allocation_effect=total_allocation,
            selection_effect=total_selection + total_interaction,
            total_active_return=(total_allocation + total_selection + total_interaction),
            top_contributors=top_contributors,
            top_detractors=top_detractors,
            narrative=narrative_raw
        )
