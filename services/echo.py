import requests
from urllib.parse import quote
import google.generativeai as genai
import json
import os
import re
from dotenv import load_dotenv
load_dotenv()


GEMENI_API = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMENI_API)
api_key= os.getenv("FIRECRAWL_API_KEY")
model = genai.GenerativeModel(model_name="gemini-2.5-flash")
CLAUDE_API = os.getenv("CLAUDE")
API_KEY = os.getenv("ECHO_API")
ENDPOINT = "https://api.firecrawl.dev/v1/scrape"

def scrape_with_delay(target_url: str, delay_ms: int = 5000):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": target_url,
        "onlyMainContent": True,
        "waitFor": delay_ms,
        "timeout": 30000,
        "formats": ["markdown"],
    }

    resp = requests.post(ENDPOINT, json=payload, headers=headers)
    resp.raise_for_status()
    result = resp.json()

    markdown = result.get("data", {}).get("markdown")
    return markdown

def get_echo_compliance(address: str):
    """Get EPA ECHO compliance data for an address"""
    
    # Build ECHO search URL
    encoded_address = quote(address)
    echo_url = f"https://echo.epa.gov/detailed-facility-report?fid=110005826302" # # p_fn={encoded_address}&p_sa={encoded_address}
    
    print(f" Searching ECHO for: {address}")
    print(f" URL: {echo_url}")
    
    # Scrape the ECHO search results
    compliance_data = scrape_with_delay(echo_url, delay_ms=10000)
    
    if compliance_data:
        print("\n" + "="*60)
        print("EPA ECHO COMPLIANCE SUMMARY")
        print("="*60)
        print(f"Address: {address}")
        print("="*60)
        print(compliance_data)
        print("="*60)
    else:
        print(f" No data found for {address}")
    
    return compliance_data

# 1. DFR URL EXTRACTION
def extract_dfr_url_from_text(formatted_text):
    """Extract DFR URL from formatted text"""
    
    # Updated patterns to handle your actual formatting
    dfr_patterns = [
        r'DFR URL:\s*(https?://echo\.epa\.gov/detailed-facility-report\?[^\s\n]+)',
        r'DFR URL:\s*(http://oaspub\.epa\.gov/enviro/[^\s\n]+)',
        r'\*\s*DFR URL:\s*(https?://echo\.epa\.gov/detailed-facility-report\?[^\s\n]+)',  # With bullet point
        r'\*\s*DFR URL:\s*(http://oaspub\.epa\.gov/enviro/[^\s\n]+)',  # With bullet point
    ]
    
    for pattern in dfr_patterns:
        match = re.search(pattern, formatted_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None

# 2. API CALL WITH EXTRACTED URL
def get_echo_data_by_url(dfr_url):
    """Get ECHO data using the extracted DFR URL"""
    
    print(f"Fetching ECHO data from: {dfr_url}")
    
    try:
        compliance_data = scrape_with_delay(dfr_url, delay_ms=10000)
        
        if compliance_data:
            print("ECHO data retrieved successfully")
            return compliance_data
        else:
            print("No data found at URL")
            return None
            
    except Exception as e:
        print(f"Error fetching ECHO data: {str(e)}")
        return None

# 3. COMPLETE WORKFLOW: EXTRACT -> API CALL -> SUMMARIZER
def process_document_for_echo(formatted_text):
    """Complete workflow: extract URL, get data, process with Claude"""
    
    dfr_url = extract_dfr_url_from_text(formatted_text)
    
    if not dfr_url:
        print("No DFR URL found in document")
        return None
    
    print(f"Found DFR URL: {dfr_url}")
    echo_raw_data = get_echo_data_by_url(dfr_url)
    
    if not echo_raw_data:
        print("No ECHO data retrieved from API")
        return None
    
    print("Processing ECHO data with Claude...")
    echo_summary = echo_claude(echo_raw_data)
    
    return echo_summary

def echo_gemeni(data, api_key=api_key, prompt="echo_prompt.txt"):
    with open(prompt, 'r', encoding='utf-8') as file:
        prompt_base = file.read()
    

    full_prompt = f"{prompt_base.strip()}\n\n---BEGIN ECHO DATA---\n{data}\n---END ECHO DATA---"
    
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key,
    }
    
    body = {
        "contents": [
            {
                "parts": [
                    {"text": full_prompt}
                ]
            }
        ]
    }
    
    response = requests.post(endpoint, headers=headers, json=body)

    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        raise Exception(f"Gemini API error {response.status_code}: {response.text}")
    
def echo_claude(data, api_key=CLAUDE_API, prompt="echo_prompt.txt"):
    """
    Send EPA ECHO compliance data to Claude 4 for analysis
    
    Args:
        data: The scraped compliance data from EPA ECHO
        api_key: Your Anthropic API key
        prompt: Path to the prompt file (default: "echo_prompt.txt")
    
    Returns:
        Formatted compliance summary from Claude
    """
    
    # Read the prompt file
    try:
        with open(prompt, 'r', encoding='utf-8') as file:
            prompt_base = file.read()
    except FileNotFoundError:
        print(f"Warning: {prompt} not found, using default prompt")
        prompt_base = """Role: You are a data formatting assistant.

Task: Summarize the compliance history for addresses found in the EPA ECHO database. Each property will have its own separate list. You will ONLY output the lists and not add any filler text.

Guidelines:
- Create lists with format: #Header: Property Name and Address, then List: Details
- ONLY include inspection, enforcement, and compliance history
- Be concise and clear"""
    
    # Construct the full prompt with clear data separation
    full_prompt = f"{prompt_base.strip()}\n\n---BEGIN ECHO DATA---\n{data}\n---END ECHO DATA---"
    
    # Claude API endpoint
    endpoint = "https://api.anthropic.com/v1/messages"
    
    # Headers for Claude API
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    
    # Request body for Claude
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
        # Make the API request
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


# Usage example:
def process_echo_with_claude(address: str, api_key=CLAUDE_API):
    """
    Complete workflow: get ECHO data and process with Claude
    
    Args:
        address: The address to search for
        api_key: Your Anthropic API key
    
    Returns:
        Formatted compliance summary
    """
    
    # Get the compliance data using your existing function
    compliance_data = get_echo_compliance(address)
    
    if compliance_data:
        print("Processing compliance data with Claude...")
        formatted_results = echo_claude(compliance_data, api_key)
        return formatted_results
    else:
        return "No compliance data found to process"


# Alternative version with inline prompt (no file needed):
def echo_claude_inline_prompt(data, api_key=CLAUDE_API):
    """
    Version with built-in prompt (no external file needed)
    """
    
    prompt_base = """Role: You are a data formatting assistant specializing in EPA compliance data.

Task: Analyze the provided EPA ECHO data and create formatted summaries for each facility found. Extract and organize compliance information clearly.

Instructions:
1. For each facility found, create a separate section
2. Use this format:
   # Facility Name - Address
   - Inspection history summary
   - Enforcement actions summary  
   - Compliance status summary
   - Any violations or penalties

3. If the data appears to be a search results page rather than detailed facility data, extract whatever facility information is available and note that detailed compliance history would require accessing individual facility pages.

4. If no facilities are found, state "No EPA-regulated facilities found at this address"

Please analyze the following EPA ECHO data:"""
    
    full_prompt = f"{prompt_base}\n\n---EPA ECHO DATA---\n{data}\n---END OF DATA---"
    
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
            return response.json()['content'][0]['text']
        else:
            return f"Claude API error {response.status_code}: {response.text}"
            
    except Exception as e:
        return f"Error: {str(e)}"

# TEST FUNCTION
def test_complete_workflow():
    """Test all three components with sample data"""
    
    sample_formatted_text = """
# Property Name and Address: 1001 N CENTRAL AVE, CASEY, IL 62420
## Header: ECHO
*   DFR URL: https://echo.epa.gov/detailed-facility-report?fid=ILR000043435
"""
    
    print("=== TESTING COMPLETE ECHO WORKFLOW ===")
    
    print("\n1. Testing DFR URL extraction...")
    url = extract_dfr_url_from_text(sample_formatted_text)
    print(f"Extracted URL: {url}")
    
    if not url:
        print("FAILED: No URL extracted")
        return
    
    print("\n2. Testing complete workflow...")
    result = process_document_for_echo(sample_formatted_text)
    
    if result:
        print("SUCCESS: Complete workflow working")
        print(f"Summary length: {len(result)} characters")
        print(f"First 200 chars: {result[:200]}...")
    else:
        print("FAILED: Complete workflow failed")
    
    return result
     
"""
def main():
    file = "Users/clarckdorcent/Downloads/EDR_text_1/train_51.txt"
    result = format_with_gemini_from_file(file)
"""

if __name__ == "__main__":
    # Test the new functionality
    test_complete_workflow()
    
