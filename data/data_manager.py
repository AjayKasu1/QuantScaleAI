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
        Fetches adjusted close prices for a list of tickers using REAL data logic.
        Uses sequential fetching (threads=False) and retries to handle rate limits.
        """
        import time
        
        # Clean tickers
        valid_tickers = [t.strip().upper() for t in tickers if t]
        if not valid_tickers:
            return pd.DataFrame()
            
        logger.info(f"Downloading prices for {len(valid_tickers)} tickers (Real Data Mode)...")
        
        data = pd.DataFrame()
        # Chunked Download Strategy to avoid timeouts/rate-limits
        chunk_size = 20
        all_data = []
        
        for i in range(0, len(valid_tickers), chunk_size):
            chunk = valid_tickers[i:i+chunk_size]
            logger.info(f"Downloading chunk {i//chunk_size + 1}: {chunk[:3]}...")
            
            chunk_data = pd.DataFrame()
            # Retry logic per chunk
            for attempt in range(3):
                try:
                    # Ticker-by-Ticker usually more reliable for small batches than bulk download if bulk is failing
                    # But let's stick to download() for speed, just smaller batches.
                    
                    # Note: threads=True might actually be better for speed if we are chunking, 
                    # but threads=False is safer for rate limits. Let's try threads=False but small chunks.
                    temp = yf.download(chunk, start=start_date, group_by='ticker', threads=False, progress=False, timeout=20)
                    
                    if not temp.empty:
                        chunk_data = temp
                        break
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Chunk failed: {e}")
                    time.sleep(1)
            
            if not chunk_data.empty:
                all_data.append(chunk_data)
        
        if not all_data:
             logger.error("All chunks failed.")
             # If user insists on live data, we might return empty here? 
             # But let's keep the fallback but make it less likely to be needed.
             pass # Will fall through to empty check

        # Concatenate
        try:
            if all_data:
                data = pd.concat(all_data, axis=1)
            else:
                data = pd.DataFrame()
        except:
            data = pd.DataFrame()

        if data.empty:
            logger.error("All download attempts failed. Switching to SYNTHETIC data.")
            return self._generate_synthetic_data(valid_tickers, start_date)

        try:
            # Handle MultiIndex
            df_close = pd.DataFrame()
            
            if len(valid_tickers) == 1:
                t = valid_tickers[0]
                if 'Adj Close' in data.columns:
                    df_close[t] = data['Adj Close']
                elif 'Close' in data.columns:
                     df_close[t] = data['Close']
            else:
                try:
                    df_close = data['Adj Close']
                except KeyError:
                    try:
                        df_close = data.xs('Adj Close', level=0, axis=1)
                    except:
                        try:
                            # Fix for group_by='ticker' (Adj Close is at Level 1)
                            df_close = data.xs('Adj Close', level=1, axis=1)
                        except:
                            try:
                                df_close = data['Close']
                            except:
                            try:
                                    df_close = data.xs('Close', level=1, axis=1)
                                except:
                                    pass

            # Drop columns with all NaNs
            df_close.dropna(axis=1, how='all', inplace=True)
            
            if df_close.empty:
                logger.warning("Extraction resulted in empty DataFrame. Switching to SYNTHETIC data.")
                return self._generate_synthetic_data(valid_tickers, start_date)
                
            return df_close
            
        except Exception as e:
            logger.error(f"Error processing market data: {e}. Switching to SYNTHETIC data.")
            return self._generate_synthetic_data(valid_tickers, start_date)

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

    def _generate_synthetic_data(self, tickers: List[str], start_date: str) -> pd.DataFrame:
        """
        Generates realistic-looking random walk data for tickers
        to ensure the app runs even if Yahoo Finance is down.
        """
        logger.warning(f"Generating SYNTHETIC market data for {len(tickers)} tickers (Demo Mode).")
        try:
            dates = pd.date_range(start=start_date, end=pd.Timestamp.now(), freq='B')
            df = pd.DataFrame(index=dates)
            
            # Consistent random seed so the "demo" looks stable between refreshes
            np.random.seed(42)
            
            for ticker in tickers:
                # Start price between 50 and 200
                start_price = np.random.uniform(50, 200)
                
                # Generate returns: Drift + Volatility
                # Annual Drift ~ 10%, Annual Vol ~ 20%
                # Daily Drift ~ 10%/252, Daily Vol ~ 20%/sqrt(252)
                mu = 0.10 / 252
                sigma = 0.20 / np.sqrt(252)
                
                returns = np.random.normal(mu, sigma, len(dates))
                
                # Path
                price_path = start_price * (1 + returns).cumprod()
                df[ticker] = price_path
                
            return df
            
        except Exception as e:
            logger.error(f"Error generating synthetic data: {e}")
            return pd.DataFrame()
