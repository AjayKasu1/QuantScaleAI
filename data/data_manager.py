import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import logging
from typing import List, Dict, Optional
from core.schema import TickerData
from config import settings

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

class SectorCache:
    """
    Manages a local cache of Ticker -> Sector mappings to avoid 
    yfinance API throttling and improve speed.
    """
    def __init__(self, cache_file: str = settings.SECTOR_MAP_FILE):
        self.cache_file = cache_file
        self.sector_map = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load sector cache: {e}")
                return {}
        return {}

    def save_cache(self):
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.sector_map, f, indent=2)

    def get_sector(self, ticker: str) -> Optional[str]:
        return self.sector_map.get(ticker)

    def update_sector(self, ticker: str, sector: str):
        self.sector_map[ticker] = sector

class MarketDataEngine:
    """
    Handles robust data ingestion from diverse sources (Wikipedia, yfinance).
    Implements data cleaning and validation policies.
    """
    def __init__(self):
        self.sector_cache = SectorCache()
        
    def fetch_sp500_tickers(self) -> List[str]:
        """
        Loads S&P 500 components from a static JSON file (Production Mode).
        Eliminates dependency on Wikipedia scraping.
        """
        try:
            universe_file = os.path.join(os.path.dirname(__file__), 'sp500_universe.json')
            
            # If we happen to not have the file, use the fallback list
            if not os.path.exists(universe_file):
                logger.warning("Universe file not found. Using fallback.")
                return self._get_fallback_tickers()
                
            with open(universe_file, 'r') as f:
                universe_data = json.load(f)
                
            tickers = []
            for item in universe_data:
                ticker = item['ticker']
                sector = item['sector']
                tickers.append(ticker)
                self.sector_cache.update_sector(ticker, sector)
                
            self.sector_cache.save_cache()
            logger.info(f"Successfully loaded {len(tickers)} tickers from static universe.")
            return tickers

        except Exception as e:
            logger.error(f"Error loading universe: {e}")
            return self._get_fallback_tickers()

    def _get_fallback_tickers(self) -> List[str]:
        # Fallback for Demo Reliability
        fallback_map = {
            "AAPL": "Information Technology", "MSFT": "Information Technology", "GOOGL": "Communication Services",
            "AMZN": "Consumer Discretionary", "NVDA": "Information Technology", "META": "Communication Services",
            "TSLA": "Consumer Discretionary", "BRK-B": "Financials", "V": "Financials", "UNH": "Health Care",
            "XOM": "Energy", "JNJ": "Health Care", "JPM": "Financials", "PG": "Consumer Staples",
            "LLY": "Health Care", "MA": "Financials", "CVX": "Energy", "MRK": "Health Care",
            "HD": "Consumer Discretionary", "PEP": "Consumer Staples", "COST": "Consumer Staples"
        }
        for t, s in fallback_map.items():
            self.sector_cache.update_sector(t, s)
        return list(fallback_map.keys())

    def fetch_market_data(self, tickers: List[str], start_date: str = "2023-01-01") -> pd.DataFrame:
        """
        Fetches adjusted close prices for a list of tickers.
        """
        if not tickers:
            logger.warning("No tickers provided to fetch.")
            return pd.DataFrame()

        logger.info(f"Downloading data for {len(tickers)} tickers from {start_date}...")
        # Use yfinance download with threads
        # 'Close' is usually adjusted in newer versions or defaults
        data = yf.download(tickers, start=start_date, progress=False)
        
        if data.empty:
            logger.error("No data fetched from yfinance.")
            return pd.DataFrame()
            
        # Handle MultiIndex (Price, Ticker)
        if hasattr(data.columns, 'levels') and 'Close' in data.columns.levels[0]:
            data = data['Close']
        elif 'Close' in data.columns:
             data = data['Close']
        elif 'Adj Close' in data.columns:
            data = data['Adj Close']
        else:
            # Fallback
            logger.warning("Could not find Close/Adj Close. Using first level.")
            data = data.iloc[:, :len(tickers)] # Risky but fallback

        return self._clean_data(data)

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Applies data quality rules:
        1. Drop columns with > 10% missing data.
        2. Forward fill then Backward fill remaining NaNs.
        """
        initial_count = len(df.columns)
        
        # Rule 1: Drop > 10% missing
        missing_frac = df.isnull().mean()
        drop_cols = missing_frac[missing_frac > 0.10].index.tolist()
        df_clean = df.drop(columns=drop_cols)
        
        dropped_count = len(drop_cols)
        if dropped_count > 0:
            logger.warning(f"Dropped {dropped_count} tickers due to >10% missing data: {drop_cols[:5]}...")
            
        # Rule 2: Fill NaNs
        df_clean = df_clean.ffill().bfill()
        
        logger.info(f"Data cleaning complete. Retained {len(df_clean.columns)}/{initial_count} tickers.")
        return df_clean

    def get_sector_map(self) -> Dict[str, str]:
        return self.sector_cache.sector_map

    def fetch_market_caps(self, tickers: List[str]) -> Dict[str, float]:
        """
        Returns market caps from local static cache.
        Does NOT fetch live to avoid timeouts/rate-limits on HF Spaces.
        """
        cache_file = os.path.join(settings.DATA_DIR, "market_cap_cache.json")
        caps = {}
        
        # Load Cache
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    caps = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load cap cache: {e}")
        else:
            logger.warning("Market Cap Cache file not found! 'Smallest/Largest' strategies may fail.")
            
        # Return requested
        return {t: caps.get(t, 0) for t in tickers}
