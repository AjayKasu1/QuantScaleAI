from fastapi import FastAPI, HTTPException, Depends
from core.schema import OptimizationRequest, OptimizationResult
from main import QuantScaleSystem
import logging

app = FastAPI(title="QuantScale AI API", version="1.0.0")
logger = logging.getLogger("API")

# Singleton System
system = QuantScaleSystem()

from fastapi.responses import RedirectResponse

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Mount static files
app.mount("/static", StaticFiles(directory="api/static"), name="static")

@app.get("/")
def root():
    """Serves the AI Interface."""
    return FileResponse('api/static/index.html')

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "QuantScale AI Direct Indexing"}

@app.post("/optimize", response_model=dict)
def optimize_portfolio(request: OptimizationRequest):
    """
    Optimizes a portfolio based on exclusions and generates an AI Attribution report.
    """
    try:
        result = system.run_pipeline(request)
        if not result:
            raise HTTPException(status_code=500, detail="Pipeline failed to execute.")
        
        return {
            "client_id": request.client_id,
            "allocations": result['optimization'].weights,
            "tracking_error": result['optimization'].tracking_error,
            "attribution_narrative": result['commentary']
        }
    except Exception as e:
        logger.error(f"API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
