import logging
from huggingface_hub import InferenceClient
from core.schema import AttributionReport
from ai.prompts import SYSTEM_PROMPT, ATTRIBUTION_PROMPT_TEMPLATE
from config import settings

logger = logging.getLogger(__name__)

class AIReporter:
    """
    Generates natural language commentary using Hugging Face Inference API.
    Models used: meta-llama/Meta-Llama-3-8B-Instruct (or similar available via API).
    """
    
    def __init__(self):
        token = settings.HF_TOKEN.get_secret_value() if settings.HF_TOKEN else None
        
        if token:
            self.client = InferenceClient(token=token)
        else:
            self.client = None
            logger.warning("HF_TOKEN not found. AI features will be disabled.")
            
        # Default to a robust instruction model
        self.model_id = "meta-llama/Meta-Llama-3-8B-Instruct" 

    def generate_report(self, 
                        attribution_report: AttributionReport, 
                        excluded_sector: str) -> str:
        """
        Constructs the prompt and calls the HF API to generate the commentary.
        """
        logger.info("Generating AI Commentary...")
        
        from datetime import datetime
        # Get current date in a specific format (e.g., "February 03, 2026")
        current_date = datetime.now().strftime("%B %d, %Y")
        
        # Format the user prompt
        # We assume ATTRIBUTION_PROMPT_TEMPLATE handles the rest, but we force the date in context
        user_prompt = f"""
Current Date: {current_date}
INSTRUCTION: Start your commentary exactly with the header: "Market Commentary - {current_date}"
""" + ATTRIBUTION_PROMPT_TEMPLATE.format(
            excluded_sector=excluded_sector,
            total_active_return=attribution_report.total_active_return * 100, # Convert to %
            allocation_effect=attribution_report.allocation_effect * 100,
            selection_effect=attribution_report.selection_effect * 100,
            top_contributors=", ".join(attribution_report.top_contributors),
            top_detractors=", ".join(attribution_report.top_detractors),
            current_date=current_date # Pass date to template
        )
        
        if not self.client:
             return f"AI Commentary Unavailable. (Missing HF_TOKEN). Current Date: {current_date}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.client.chat_completion(
                model=self.model_id,
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            commentary = response.choices[0].message.content
            logger.info("AI Commentary generated successfully.")
            return commentary
            
        except Exception as e:
            logger.error(f"Failed to generate AI report: {e}")
            return "Error generating commentary. Please check API connection."
