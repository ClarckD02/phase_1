from typing import List, Dict
from pydantic import BaseModel

class SummarizationResponse(BaseModel):
    filename: str
    text: str
    entities: List[Dict]
    formatted: str   # Gemini output (often JSON-as-string)
    summary: str 
