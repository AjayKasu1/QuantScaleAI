import logging
import os
import json
import requests
from core.schema import AttributionReport
from ai.prompts import SYSTEM_PROMPT, ATTRIBUTION_PROMPT_TEMPLATE, INTENT_PARSER_SYSTEM_PROMPT
from config import settings

logger = logging.getLogger(__name__)

class AIReporter:
    """
    Generates natural language commentary using Bytez AI API.
    Replaces Hugging Face InferenceClient for more reliable performance.
    """
    
    def __init__(self):
        # Read the API key from environment (prioritize settings/os.environ)
        self.api_key = settings.BYTEZ_API_KEY.get_secret_value() if settings.BYTEZ_API_KEY else os.environ.get("BYTEZ_API_KEY")
        
        if not self.api_key:
            logger.warning("BYTEZ_API_KEY not found in environment. AI features will be disabled.")
            
        # Using Llama 3 8B Instruct as the baseline model on Bytez
        self.base_url = "https://api.bytez.com/models/v2"
        self.model_path = "meta-llama/Meta-Llama-3-8B-Instruct"
        self.endpoint = f"{self.base_url}/{self.model_path}"

    def _call_bytez(self, messages: list, max_tokens: int = 500, temperature: float = 0.7, top_p: float = 0.9) -> str:
        """
        Helper to make the POST request to Bytez.
        """
        if not self.api_key:
            return ""

        headers = {
            "Content-Type": "application/json",
            "Authorization": self.api_key
        }
        
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "response_format": {"type": "json_object"} if temperature < 0.2 else None
        }

        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            # Handle different common response formats
            if isinstance(result, dict):
                if "choices" in result: # Standard OpenAI format
                    return result["choices"][0]["message"]["content"]
                if "output" in result and isinstance(result["output"], dict) and "content" in result["output"]: # Bytez format
                    return result["output"]["content"]
                return str(result)
            elif isinstance(result, str):
                return result
            else:
                return str(result)
                
        except Exception as e:
            logger.error(f"Bytez API Call Failed: {e}")
            return ""

    def parse_intent(self, user_prompt: str) -> list:
        """
        Uses Bytez AI to map user prompt to a list of exact GICS sectors to exclude.
        Highly deterministic (temp=0.1) with robust regex extraction.
        """
        logger.info(f"Parsing intent with Bytez for prompt: {user_prompt[:50]}...")
        
        messages = [
            {"role": "system", "content": INTENT_PARSER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse: '{user_prompt}'"}
        ]
        
        try:
            # Intent Parser uses low temperature and top_p for determinism
            content = self._call_bytez(
                messages, 
                max_tokens=100, 
                temperature=0.1
            )
            
            if not content:
                logger.warning("Empty response from Bytez for Intent Parsing. Defaulting to [].")
                return []

            # Robust Regex Fallback Extraction
            import re
            # Look for the JSON list [ ... ]
            match = re.search(r'\[.*\]', content.strip(), re.DOTALL)
            if match:
                extracted_json = match.group(0)
                try:
                    return json.loads(extracted_json)
                except json.JSONDecodeError as je:
                    logger.error(f"JSON Decode Error after extraction: {je}")
                    return []
            
            logger.warning(f"No JSON list found in response: {content[:100]}...")
            return []
            
        except Exception as e:
            logger.error(f"Intent Parsing Error (Bytez): {e}")
            return []

    def generate_report(self, 
                        attribution_report: AttributionReport, 
                        excluded_sector: str,
                        tracking_error: float = 0.0) -> str:
        """
        Constructs the prompt and calls the Bytez API to generate the commentary.
        """
        logger.info("Generating AI Commentary with Bytez...")
        
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")
        
        # Grounding check: If Tracking Error is 0, we are in replication mode
        is_replication = attribution_report.total_active_return == 0
        
        # Format the user prompt
        user_prompt = f"""
Current Date: {current_date}
Portfolio Metadata:
- Sector Exclusions: {excluded_sector}
- Alpha (Active Return): {attribution_report.total_active_return * 100:.2f}%
- Total Tracking Error: {tracking_error * 100:.4f}%
- Full Replication Mode: {is_replication}

## DATA TABLES:
**Contributors/Detractors**:
{json.dumps(attribution_report.top_contributors[:5], indent=2)}
{json.dumps(attribution_report.top_detractors[:5], indent=2)}

**Sector Positioning**:
{json.dumps(attribution_report.sector_exposure, indent=2)}
"""
        
        if not self.api_key:
             return f"AI Commentary Unavailable. (Missing BYTEZ_API_KEY). Current Date: {current_date}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            commentary = self._call_bytez(messages, max_tokens=600, temperature=0.7)
            
            if not commentary:
                return "AI Commentary generation timed out or failed. Please try again."
                
            return commentary.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate Bytez report: {e}")
            return "Error generating commentary via Bytez AI. Check API key and connectivity."
