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

    def _call_bytez(self, messages: list, max_tokens: int = 500, temperature: float = 0.7) -> str:
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
            "temperature": temperature
        }

        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            # Handle different common response formats
            if isinstance(result, dict) and "choices" in result:
                return result["choices"][0]["message"]["content"]
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
        """
        logger.info(f"Parsing intent with Bytez for prompt: {user_prompt[:50]}...")
        
        messages = [
            {"role": "system", "content": INTENT_PARSER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this prompt for sector exclusions: '{user_prompt}'"}
        ]
        
        try:
            content = self._call_bytez(messages, max_tokens=100, temperature=0.0)
            if not content:
                logger.warning("Empty response from Bytez for Intent Parsing. Returning empty list.")
                return []

            # Clean content for JSON extraction
            import re
            match = re.search(r'\[.*\]', content.strip(), re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return []
            
        except Exception as e:
            logger.error(f"Intent Parsing Error (Bytez): {e}")
            return []

    def generate_report(self, 
                        attribution_report: AttributionReport, 
                        excluded_sector: str) -> str:
        """
        Constructs the prompt and calls the Bytez API to generate the commentary.
        """
        logger.info("Generating AI Commentary with Bytez...")
        
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")
        
        # Format the user prompt
        user_prompt = f"""
Current Date: {current_date}
INSTRUCTION: Start your commentary exactly with the header: "Market Commentary - {current_date}"
""" + ATTRIBUTION_PROMPT_TEMPLATE.format(
            excluded_sector=excluded_sector,
            total_active_return=attribution_report.total_active_return * 100,
            allocation_effect=attribution_report.allocation_effect * 100,
            selection_effect=attribution_report.selection_effect * 100,
            top_contributors=json.dumps(attribution_report.top_contributors, indent=2),
            top_detractors=json.dumps(attribution_report.top_detractors, indent=2),
            sector_positioning=json.dumps(attribution_report.sector_exposure, indent=2),
            current_date=current_date
        )
        
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
                
            return commentary
            
        except Exception as e:
            logger.error(f"Failed to generate Bytez report: {e}")
            return "Error generating commentary via Bytez AI. Check API key and connectivity."
