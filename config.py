import os
from typing import Optional
from pydantic import BaseModel, Field, SecretStr

class Settings(BaseModel):
    """
    Application Configuration.
    Loads from environment variables via os.getenv.
    """
    
    # API Keys
    HF_TOKEN: Optional[SecretStr] = Field(default_factory=lambda: SecretStr(os.getenv("HF_TOKEN", "")) if os.getenv("HF_TOKEN") else None, description="Hugging Face API Token")
    
    # Data Configuration
    DATA_CACHE_DIR: str = Field(default="./data_cache", description="Directory to store cached market data")
    SECTOR_MAP_FILE: str = Field(default="./data/sector_map.json", description="Path to sector mapping cache")
    
    # Optimization Defaults
    MAX_WEIGHT: float = Field(default=0.05, description="Maximum weight for a single asset")
    MIN_WEIGHT: float = Field(default=0.00, description="Minimum weight for a single asset")
    
    # Universe
    BENCHMARK_TICKER: str = Field(default="^GSPC", description="Benchmark Ticker (S&P 500)")
    
    # System
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")


# Global settings instance
try:
    settings = Settings()
except Exception as e:
    print(f"WARNING: Settings failed to load. Using defaults/env vars might be missing: {e}")
    # Fallback to empty settings if possible or re-raise if critical
    # For now, let's allow it to crash safely or provide a dummy
    # But if HF_TOKEN is None, the AI feature will just fail gracefully later
    settings = Settings(HF_TOKEN=None)
