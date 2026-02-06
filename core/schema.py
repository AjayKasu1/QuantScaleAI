from typing import List, Dict, Optional
from pydantic import BaseModel, Field, validator
import pandas as pd
from datetime import date

class TickerData(BaseModel):
    """
    Represents a single stock's metadata and price history.
    """
    symbol: str
    sector: str
    price_history: Dict[str, float] = Field(default_factory=dict, description="Date (ISO) -> Adj Close Price")
    
    @property
    def latest_price(self) -> float:
        if not self.price_history:
            return 0.0
        # Sort by date key and get last value
        return self.price_history[sorted(self.price_history.keys())[-1]]

class OptimizationRequest(BaseModel):
    """
    User request for portfolio optimization.
    """
    client_id: str
    initial_investment: float = 100000.0
    excluded_sectors: List[str] = Field(default_factory=list, description="List of sectors to exclude (e.g., ['Energy'])")
    excluded_tickers: List[str] = Field(default_factory=list, description="List of specific tickers to exclude (e.g., ['AMZN'])")
    max_weight: Optional[float] = Field(None, description="Maximum weight for any single asset (e.g., 0.05)")
    strategy: Optional[str] = Field(None, description="Global Filter Strategy: 'smallest_market_cap' or 'largest_market_cap'")
    top_n: Optional[int] = Field(None, description="Number of assets to select for strategy (e.g. 50)")
    benchmark: str = "^GSPC"

    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "Demo_User_1",
                "initial_investment": 100000.0,
                "excluded_sectors": ["Energy"],
                "excluded_tickers": ["AMZN"],
                "benchmark": "^GSPC"
            }
        }

class OptimizationResult(BaseModel):
    """
    Output of the optimization engine.
    """
    weights: Dict[str, float] = Field(..., description="Ticker -> Optimal Weight")
    tracking_error: float
    status: str
    
    @validator('weights')
    def validate_weights(cls, v):
        # Filter out near-zero weights for cleanliness
        return {k: val for k, val in v.items() if val > 0.0001}

class TaxLot(BaseModel):
    """
    A specific purchase lot of a stock.
    """
    symbol: str
    purchase_date: date
    quantity: int
    cost_basis_per_share: float
    current_price: float

    @property
    def unrealized_pl(self) -> float:
        return (self.current_price - self.cost_basis_per_share) * self.quantity

    @property
    def is_loss(self) -> bool:
        return self.unrealized_pl < 0
    
    @property
    def loss_percentage(self) -> float:
         if self.cost_basis_per_share == 0: return 0.0
         return (self.current_price - self.cost_basis_per_share) / self.cost_basis_per_share

class HarvestOpportunity(BaseModel):
    """
    A suggestion to harvest a tax loss.
    """
    sell_ticker: str
    buy_proxy_ticker: str
    quantity: int
    estimated_loss_harvested: float
    reason: str
    
class AttributionReport(BaseModel):
    """
    Brinson Attribution Data.
    """
    allocation_effect: float
    selection_effect: float
    total_active_return: float
    top_contributors: List[Dict]
    top_detractors: List[Dict]
    narrative: str
