import requests
import json
import os
import re
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

class EchoCompliance:
    """Static class for EPA ECHO compliance data processing"""
    
    # Configuration
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    CLAUDE_API_KEY = os.getenv("CLAUDE") or os.getenv("ANTHROPIC_API_KEY")
    FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"
    ECHO_API_KEY = os.getenv("ECHO_API")
    
    @staticmethod
    def scrape_with_delay(target_url: str, delay_ms: int = 5000):
        """Scrape URL using Firecrawl API"""
        headers = {
            "Authorization": f"Bearer {EchoCompliance.ECHO_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": target_url,
            "onlyMainContent": True,
            "waitFor": delay_ms,
            "timeout": 30000,
            "formats": ["markdown"],
        }

        resp = requests.post(EchoCompliance.FIRECRAWL_ENDPOINT, json=payload, headers=headers)
        resp.raise_for_status()
        result = resp.json()

        return result.get("data", {}).get("markdown")
    
    @staticmethod
    def extract_dfr_url_from_raw_text(raw_text: str):
        """Extract DFR URL from raw text before any formatting"""
        patterns = [
            r'DFR URL:\s*(https?://echo\.epa\.gov/detailed-facility-report\?[^\s\n]+)',
            r'DFR URL:\s*(http://echo\.epa\.gov/detailed-facility-report\?[^\s\n]+)',
            r'DFR URL:\s*(http://oaspub\.epa\.gov/enviro/[^\s\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    @staticmethod
    def get_echo_data_by_url(dfr_url: str):
        """Get ECHO compliance data using DFR URL"""
        print(f"Fetching ECHO data from: {dfr_url}")
        
        try:
            compliance_data = EchoCompliance.scrape_with_delay(dfr_url, delay_ms=10000)
            
            if compliance_data:
                print("ECHO data retrieved successfully")
                return compliance_data
            else:
                print("No data found at URL")
                return None
                
        except Exception as e:
            print(f"Error fetching ECHO data: {str(e)}")
            return None
    
    @staticmethod
    def process_with_claude(echo_data: str, api_key: str = None):
        """Process ECHO data with Claude using standardized prompt"""
        
        api_key = api_key or EchoCompliance.CLAUDE_API_KEY
        
        if not api_key:
            raise ValueError("Claude API key not found. Set CLAUDE or ANTHROPIC_API_KEY environment variable.")
        
        # Standardized ECHO processing prompt
        prompt_base = """Role

You are a data formatting assistant.

Task

Your task is to summarize the compliance history for addresses found in the EPA ECHO database. Each property will have its own separate list. You will ONLY output the lists and not add any filler text.

Guidelines

Follow these guidelines to create the lists:

List Structure:
#Header: Property Name and Address
List: Details

ONLY include the following specific details in the lists:
- Summarize the inspection, enforcement, and compliance history of each address

Below is the extracted EPA ECHO data that you need to analyze and format:

---BEGIN ECHO DATA---"""
        
        full_prompt = f"{prompt_base}\n{echo_data}\n---END ECHO DATA---"
        
        # Claude API call
        endpoint = "https://api.anthropic.com/v1/messages"
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        
        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4000,
            "messages": [
                {
                    "role": "user",
                    "content": full_prompt
                }
            ]
        }
        
        try:
            response = requests.post(endpoint, headers=headers, json=body)
            
            if response.status_code == 200:
                response_data = response.json()
                return response_data['content'][0]['text']
            else:
                error_msg = f"Claude API error {response.status_code}: {response.text}"
                print(error_msg)
                return f"Error: {error_msg}"
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            print(error_msg)
            return f"Error: {error_msg}"
        
        except KeyError as e:
            error_msg = f"Unexpected response format: {str(e)}"
            print(error_msg)
            return f"Error: {error_msg}"
        
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON response: {str(e)}"
            print(error_msg)
            return f"Error: {error_msg}"
    
    @staticmethod
    def get_compliance_summary(raw_text: str):
        """Complete workflow: extract URL from raw text, fetch data, process with Claude"""
        
        # Step 1: Extract DFR URL from raw text
        dfr_url = EchoCompliance.extract_dfr_url_from_raw_text(raw_text)
        
        if not dfr_url:
            print("No DFR URL found in raw text")
            return None
        
        print(f"Found DFR URL: {dfr_url}")
        
        # Step 2: Fetch ECHO data
        echo_raw_data = EchoCompliance.get_echo_data_by_url(dfr_url)
        
        if not echo_raw_data:
            print("No ECHO data retrieved from API")
            return None
        
        # Step 3: Process with Claude
        print("Processing ECHO data with Claude...")
        echo_summary = EchoCompliance.process_with_claude(echo_raw_data)
        
        return echo_summary
    
    @staticmethod
    def test_integration():
        """Test the complete ECHO integration workflow"""
        
        sample_raw_text = """
        ECHO:
            Envid:                                   1001077109
            Registry ID:                             110008338423
            DFR URL:                                 http://echo.epa.gov/detailed-facility-report?fid=110008338423
        """
        
        print("=== TESTING ECHO COMPLIANCE CLASS ===")
        
        # Test URL extraction
        print("\n1. Testing DFR URL extraction...")
        url = EchoCompliance.extract_dfr_url_from_raw_text(sample_raw_text)
        print(f"Extracted URL: {url}")
        
        if not url:
            print("FAILED: No URL extracted")
            return
        
        # Test complete workflow
        print("\n2. Testing complete workflow...")
        result = EchoCompliance.get_compliance_summary(sample_raw_text)
        
        if result:
            print("SUCCESS: Complete workflow working")
            print(f"Summary length: {len(result)} characters")
            print(f"First 200 chars: {result[:200]}...")
        else:
            print("FAILED: Complete workflow failed")
        
        return result

# Usage examples:
if __name__ == "__main__":
    # Test the integration
    results = EchoCompliance.test_integration()
    print(results)
    
    # Or use individual methods:
    # url = EchoCompliance.extract_dfr_url_from_raw_text(raw_text)
    # data = EchoCompliance.get_echo_data_by_url(url)
    # summary = EchoCompliance.process_with_claude(data)