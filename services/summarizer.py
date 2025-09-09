from anthropic import Anthropic
import os
from summarization_prompt import (
    build_section_523_prompt,
    build_section_524_prompt,
    parse_extracted_address,
    DEFAULT_DATABASES_LIST
)
from dotenv import load_dotenv
load_dotenv()

class Summarizer:
    _client: Anthropic = None
    _model: str = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20240620")

    @classmethod
    def _get_client(cls) -> Anthropic:
        if cls._client is None:
            api_key = os.getenv("CLAUDE") or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("Missing Anthropic API key. Set CLAUDE or ANTHROPIC_API_KEY.")
            cls._client = Anthropic(api_key=api_key)
        return cls._client

    @classmethod
    async def generate_section_521_streaming(
        cls,
        websocket,
        formatted_text: str,
        databases_list: list[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1500,
    ) -> dict:
        """
        Generate Section 5.2.1 with streaming and extract subject property address.
        """
        dbs = databases_list or DEFAULT_DATABASES_LIST
        system_prompt = build_section_523_prompt(dbs)

        client = cls._get_client()
        
        full_content = ""
        buffer = ""
        
        stream = client.messages.stream(
            model=cls._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": formatted_text}],
        )
        
        with stream as message_stream:
            for chunk in message_stream:
                if chunk.type == "content_block_delta":
                    text_chunk = chunk.delta.text
                    full_content += text_chunk
                    buffer += text_chunk
                    
                    # Send buffer when we have complete words or hit punctuation
                    if any(char in buffer for char in [' ', '\n', '.', '!', '?', ':', ';', ',']):
                        await websocket.send_text(buffer)
                        buffer = ""
        
        # Send any remaining buffer content
        if buffer:
            await websocket.send_text(buffer)
        
        content = full_content.strip()
        subject_address = parse_extracted_address(content)
        
        return {
            "section_content": content,
            "subject_address": subject_address
        }

    @classmethod
    async def generate_section_522_streaming(
        cls,
        websocket,
        formatted_text: str,
        subject_address: str,
        groundwater_flow: str = None,
        distance_data: dict = None,
        databases_list: list[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> str:
        """
        Generate Section 5.2.2 with streaming.
        """
        dbs = databases_list or DEFAULT_DATABASES_LIST
        system_prompt = build_section_524_prompt(dbs)
        
        user_content = f"Subject Property Address: {subject_address}\n"
        if groundwater_flow:
            user_content += f"Groundwater Flow Direction: {groundwater_flow}\n"
        if distance_data:
            user_content += f"Distance Data: {distance_data}\n"
        user_content += f"\nStructured content:\n{formatted_text}"

        client = cls._get_client()
        
        full_content = ""
        buffer = ""
        
        stream = client.messages.stream(
            model=cls._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        
        with stream as message_stream:
            for chunk in message_stream:
                if chunk.type == "content_block_delta":
                    text_chunk = chunk.delta.text
                    full_content += text_chunk
                    buffer += text_chunk
                    
                    # Send buffer when we have complete words or hit punctuation
                    if any(char in buffer for char in [' ', '\n', '.', '!', '?', ':', ';', ',']):
                        await websocket.send_text(buffer)
                        buffer = ""
        
        # Send any remaining buffer content
        if buffer:
            await websocket.send_text(buffer)
        
        return full_content.strip()

    @classmethod
    async def intelligent_chat_streaming(
        cls,
        websocket,
        context: str,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> str:
        """
        Handle intelligent chat with streaming.
        """
        client = cls._get_client()
        
        full_content = ""
        buffer = ""
        
        stream = client.messages.stream(
            model=cls._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": context}]
        )
        
        with stream as message_stream:
            for chunk in message_stream:
                if chunk.type == "content_block_delta":
                    text_chunk = chunk.delta.text
                    full_content += text_chunk
                    buffer += text_chunk
                    
                    # Send buffer when we have complete words or hit punctuation
                    if any(char in buffer for char in [' ', '\n', '.', '!', '?', ':', ';', ',']):
                        await websocket.send_text(buffer)
                        buffer = ""
        
        # Send any remaining buffer content
        if buffer:
            await websocket.send_text(buffer)
        
        return full_content.strip()