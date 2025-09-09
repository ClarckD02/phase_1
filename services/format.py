import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv()


class FormatText:
    _model = None

    @classmethod
    def _get_model(cls, model_name="gemini-2.0-flash"):
        if cls._model is None:
            api_key = os.getenv("GEMINI_API_KEY")  
            if not api_key:
                raise RuntimeError("Missing GEMINI_API_KEY")
            genai.configure(api_key=api_key)
            cls._model = genai.GenerativeModel(model_name)
        return cls._model

    @classmethod
    def format_with_gemini_from_file(cls, extracted_text: str, prompt_path="formatting_prompt.txt") -> str:
        with open(prompt_path, "r", encoding="utf-8") as f:
            base_prompt = f.read().strip()

        full_prompt = f"{base_prompt}\n\n{extracted_text}"

        model = cls._get_model()
        resp = model.generate_content(full_prompt)
        return resp.text or ""
    
