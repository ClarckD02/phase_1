# app/domain/ports.py
from __future__ import annotations
from typing import Protocol, List, Dict, Optional, runtime_checkable


# =============== Ports (interfaces) ===============

@runtime_checkable
class ExtractorPort(Protocol):
    def extraction(self, pdf_bytes: bytes, filename: str) -> Dict:
        """
        Return a dict with at least: {"filename": str, "text": str}
        """
        ...


@runtime_checkable
class NERPort(Protocol):
    def extract_entities(self, text: str) -> List[Dict]:
        """
        Return a list of entities: [{"text": str, "label": str, "start": int, "end": int}, ...]
        """
        ...


@runtime_checkable
class FormatterPort(Protocol):
    def format_with_gemini_from_file(
        self,
        extracted_text: str,
        prompt_path: str = "formatting_prompt.txt",
    ) -> str:
        """
        Return a formatted/structured string (often JSON-as-string).
        """
        ...


@runtime_checkable
class SummarizerPort(Protocol):
    def summarize_with_claude(
        self,
        formatted_text: str,
        databases_list: Optional[List[str]] = None,
        temperature: float = 0.0,
        max_tokens: int = 1500,
    ) -> str:
        """
        Return a natural-language summary string.
        """
        ...


# =============== Test Fakes (lightweight, deterministic) ===============

class FakeExtractor(ExtractorPort):
    def extraction(self, pdf_bytes: bytes, filename: str) -> Dict:
        # decode bytes if they're utf-8-ish; otherwise stub fixed text
        try:
            text = pdf_bytes.decode("utf-8")
        except Exception:
            text = "FAKE_EXTRACTED_TEXT"
        return {"filename": filename, "text": text}


class FakeNER(NERPort):
    def extract_entities(self, text: str) -> List[Dict]:
        # trivial rule: any ALLCAPS word becomes an ENTITY
        ents: List[Dict] = []
        i = 0
        for token in text.split():
            if token.isupper() and token.isalpha():
                start = text.find(token, i)
                end = start + len(token)
                ents.append({"text": token, "label": "FAKE_ENTITY", "start": start, "end": end})
                i = end
            else:
                i += len(token) + 1
        return ents


class FakeFormatter(FormatterPort):
    def format_with_gemini_from_file(self, extracted_text: str, prompt_path: str = "formatting_prompt.txt") -> str:
        # return a tiny JSON-shaped string to mimic structured output
        return (
            '{"title":"Fake Document","sections":[{"heading":"Intro","summary":"'
            + extracted_text[:80].replace('"', '\\"')
            + '"}]}'
        )


class FakeSummarizer(SummarizerPort):
    def summarize_with_claude(
        self,
        formatted_text: str,
        databases_list: Optional[List[str]] = None,
        temperature: float = 0.0,
        max_tokens: int = 1500,
    ) -> str:
        # deterministic "summary" that includes a hash of the input length
        return f"FAKE_SUMMARY: formatted_len={len(formatted_text)} dbs={len(databases_list or [])}"


# =============== Example orchestrator for tests ===============

def process_document_for_test(
    extractor: ExtractorPort,
    ner: NERPort,
    formatter: FormatterPort,
    summarizer: SummarizerPort,
    pdf_bytes: bytes,
    filename: str,
) -> Dict:
    """
    Minimal pipeline used in unit tests. Pure DI through ports.
    """
    extraction = extractor.extraction(pdf_bytes, filename)
    text = extraction.get("text", "")
    entities = ner.extract_entities(text)
    formatted = formatter.format_with_gemini_from_file(text)
    summary = summarizer.summarize_with_claude(formatted)

    return {
        "filename": filename,
        "text": text,
        "entities": entities,
        "formatted": formatted,
        "summary": summary,
    }
