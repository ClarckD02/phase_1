from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi import FastAPI, WebSocket, Depends
from fastapi.responses import HTMLResponse
from services.summarizer import Summarizer
from services.extract_pdfs import ExtractPdfs
from services.format import FormatText
from services.distance_calculator import tool_calculate_distances
from services.echo_information import EchoCompliance

import json
import base64
from fastapi import WebSocketDisconnect
router = APIRouter(prefix="/testing", tags=["testing"])

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Environmental Assessment Chat</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .upload-section { border: 2px dashed #ccc; padding: 20px; margin: 20px 0; text-align: center; }
            #messages { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; margin: 10px 0; background: #f9f9f9; }
            .message { margin: 5px 0; padding: 5px; }
            .user { background: #e3f2fd; border-radius: 5px; padding: 8px; }
            .assistant { background: #f3e5f5; border-radius: 5px; padding: 8px; }
            button { padding: 8px 16px; margin: 5px; }
            #messageText { width: 70%; padding: 8px; }
        </style>
    </head>
    <body>
        <h1>Environmental Assessment Assistant</h1>
        
        <div class="upload-section">
            <h3>Upload PDF Document</h3>
            <input type="file" id="fileInput" accept=".pdf" />
            <button onclick="uploadFile()">Upload PDF</button>
        </div>
        
        <div id='messages'></div>
        
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" placeholder="Type a message..." autocomplete="off"/>
            <button type="submit">Send</button>
        </form>
        
        <script>
            var ws = new WebSocket("ws://localhost:8000/testing/realtest");
            var currentStreamingMessage = null;
            
            ws.onopen = function() {
                addMessage("Connected to Environmental Assessment Assistant", "assistant");
            };
            
            ws.onmessage = function(event) {
                var text = event.data;
                
                // Check if this looks like the start of a new response
                if (text.includes("---") || text.includes("Processing") || text.includes("You:") || text.includes("Uploading:") || text.includes("Error:") || text.includes("Please") || text.includes("I have") || text.includes("Ready to") || text.includes("Using groundwater") || text.includes("Calculating") || text.includes("Generating") || text.includes("Received") || text.includes("Failed to") || text.includes("Extracted address:") || text.includes("Found EPA ECHO") || text.includes("Fetching") || text.includes("Enhanced compliance")) {
                    // Start a new message
                    currentStreamingMessage = null;
                    addMessage(text, "assistant");
                } else {
                    // This is likely a streaming chunk, append to current message
                    if (currentStreamingMessage) {
                        appendToMessage(text);
                    } else {
                        // No current streaming message, start a new one
                        addMessage(text, "assistant");
                    }
                }
            };
            
            ws.onerror = function(error) {
                addMessage("Connection error", "assistant");
            };
            
            function addMessage(text, type) {
                var messages = document.getElementById('messages');
                var message = document.createElement('div');
                message.className = 'message ' + type;
                message.textContent = text;
                messages.appendChild(message);
                messages.scrollTop = messages.scrollHeight;
                
                // If this is an assistant message, set it as the current streaming target
                if (type === 'assistant') {
                    currentStreamingMessage = message;
                }
            }
            
            function appendToMessage(text) {
                if (currentStreamingMessage) {
                    currentStreamingMessage.textContent += text;
                    var messages = document.getElementById('messages');
                    messages.scrollTop = messages.scrollHeight;
                }
            }
            
            function uploadFile() {
                var fileInput = document.getElementById('fileInput');
                var file = fileInput.files[0];
                
                if (!file) {
                    alert('Please select a PDF file');
                    return;
                }
                
                if (file.type !== 'application/pdf') {
                    alert('Please select a PDF file');
                    return;
                }
                
                addMessage("Uploading: " + file.name, "user");
                currentStreamingMessage = null; // Reset streaming for new interaction
                
                var reader = new FileReader();
                reader.onload = function(e) {
                    var base64Data = e.target.result.split(',')[1];
                    var message = {
                        type: "file_upload",
                        filename: file.name,
                        data: base64Data
                    };
                    ws.send(JSON.stringify(message));
                };
                reader.readAsDataURL(file);
            }
            
            function sendMessage(event) {
                var input = document.getElementById("messageText");
                if (input.value.trim() === '') return;
                
                var message = {
                    type: "chat",
                    content: input.value
                };
                
                addMessage("You: " + input.value, "user");
                currentStreamingMessage = null; // Reset streaming for new interaction
                ws.send(JSON.stringify(message));
                input.value = '';
                event.preventDefault();
            }
        </script>
    </body>
</html>
"""

async def get_extractor():
    return ExtractPdfs()

# REMOVED: ner_model and get_ner() function

async def get_formatter():
    return FormatText()

async def get_summarizer():
    return Summarizer()

@router.get("/")
async def get():
    return HTMLResponse(html)

@router.websocket("/realtest")
async def websocket_endpoint(
    websocket: WebSocket,
    extractor: ExtractPdfs = Depends(get_extractor),
    # ner: NER = Depends(get_ner),  # REMOVED
    formatter: FormatText = Depends(get_formatter),
    summarizer: Summarizer = Depends(get_summarizer)
):
    await websocket.accept()
    
    session = {
        "main_document": None,
        "surrounding_documents": [],
        "subject_address": None,
        "section_522": None,
        "workflow_stage": "awaiting_main_doc"
    }
    
    await websocket.send_text("Hello! I'm your environmental assessment assistant. Upload a PDF document to begin generating sections 5.2.3 and 5.2.4.")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "file_upload":
                    await process_pdf(websocket, message, session, extractor, formatter, summarizer)  # REMOVED ner parameter
                elif message_type == "chat":
                    await handle_intelligent_chat(websocket, message, session, summarizer)
                    
            except json.JSONDecodeError:
                await websocket.send_text("Please upload a PDF or use the chat interface.")
                
    except WebSocketDisconnect:
        pass

async def process_pdf(websocket, message, session, extractor, formatter, summarizer):  # REMOVED ner parameter
    await websocket.send_text("Processing PDF...")
    
    try:
        pdf_bytes = base64.b64decode(message["data"])
        filename = message["filename"]
        extraction = extractor.extraction(pdf_bytes, filename=filename)
        raw_text = extraction.get("text", "").strip()
        
        if not raw_text:
            await websocket.send_text("Could not extract text from PDF")
            return
        
        # Check for ECHO DFR URL in raw text before formatting
        dfr_url = EchoCompliance.extract_dfr_url_from_raw_text(raw_text)
        echo_summary = None
        
        if dfr_url:
            await websocket.send_text("Found EPA ECHO DFR URL - fetching enhanced compliance data...")
            try:
                # Make the API call
                echo_raw_data = EchoCompliance.get_echo_data_by_url(dfr_url)
                if echo_raw_data:
                    await websocket.send_text("Processing ECHO data with Claude...")
                    echo_summary = EchoCompliance.process_with_claude(echo_raw_data)
                    await websocket.send_text("Enhanced compliance data retrieved successfully.")
                else:
                    await websocket.send_text("No ECHO data available for this facility.")
            except Exception as e:
                await websocket.send_text(f"Error fetching ECHO data: {str(e)}")
                
        # REMOVED: entities = ner.extract_entities(raw_text)
        formatted = formatter.format_with_gemini_from_file(raw_text)
        
        # Check if this is main document or surrounding property
        if not session.get("main_document"):
            # This is the main property document
            await websocket.send_text("Processing main property document...")
            
            # Generate Section 5.2.1 with ECHO enhancement if available
            await websocket.send_text("--- Section 5.2.3 ---")
            
            if echo_summary:
                # Enhanced context for Section 5.2.1
                enhanced_context = f"""Environmental Database Document Content:
{formatted}

Enhanced EPA ECHO Compliance Summary:
{echo_summary}

Instructions: Generate Section 5.2.3 incorporating both the environmental database information and the enhanced EPA ECHO compliance summary. When the document mentions ECHO database listings, enhance those entries with the detailed compliance information provided above. Integrate the ECHO compliance data seamlessly into the facility summary to provide comprehensive environmental assessment information."""
                
                result_521 = await summarizer.generate_section_521_streaming(
                    websocket,
                    enhanced_context
                )
            else:
                # Standard Section 5.2.1 without ECHO enhancement
                result_521 = await summarizer.generate_section_521_streaming(
                    websocket,
                    formatted
                )
            
            session["main_document"] = {
                "filename": filename,
                "text": raw_text,
                "formatted": formatted,
                # "entities": entities,  # REMOVED
                "dfr_url": dfr_url,
                "echo_summary": echo_summary
            }
            session["section_521"] = result_521["section_content"]
            session["subject_address"] = result_521.get("subject_address")
            session["workflow_stage"] = "can_upload_surrounding"
            
            if session["subject_address"]:
                await websocket.send_text(f"Extracted address: {session['subject_address']}")
            
            if echo_summary:
                await websocket.send_text("Section 5.2.3 generated with enhanced EPA ECHO compliance data!")
            else:
                await websocket.send_text("Section 5.2.3 complete!")
                
            await websocket.send_text("You can now upload surrounding properties PDFs to enable Section 5.2.4 generation.")
            
        else:
            # This is a surrounding property document
            await websocket.send_text(f"Processing surrounding property document: {filename}")
            
            surrounding_doc = {
                "filename": filename,
                "text": raw_text,
                "formatted": formatted,
                # "entities": entities,  # REMOVED
                "dfr_url": dfr_url,
                "echo_summary": echo_summary
            }
            session["surrounding_documents"].append(surrounding_doc)
            
            await websocket.send_text(f"Surrounding property '{filename}' processed. Total surrounding documents: {len(session['surrounding_documents'])}")
            await websocket.send_text("You can upload more surrounding properties or ask me to generate Section 5.2.4.")
        
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")

def extract_groundwater_direction(text):
    """Extract groundwater flow direction from user message"""
    text_lower = text.lower()
    
    direction_patterns = {
        'north': 'N', 'south': 'S', 'east': 'E', 'west': 'W',
        'northeast': 'NE', 'northwest': 'NW', 'southeast': 'SE', 'southwest': 'SW',
        'ne': 'NE', 'nw': 'NW', 'se': 'SE', 'sw': 'SW',
        'n ': 'N', 'e ': 'E', 's ': 'S', 'w ': 'W'
    }
    
    for pattern, direction in direction_patterns.items():
        if pattern in text_lower:
            return direction
    
    return None
        
async def handle_intelligent_chat(websocket, message, session, summarizer):
    user_question = message.get("content", "").strip()
    
    if not session.get("main_document"):
        await websocket.send_text("Please upload a PDF document first so I can answer questions about it.")
        return
    
    # Check if user wants Section 5.2.2
    if any(phrase in user_question.lower() for phrase in ["section 5.2.4", "5.2.4", "surrounding properties", "generate 5.2.2"]):
        
        if not session.get("subject_address"):
            await websocket.send_text("I need the subject property address first. The main document didn't contain extractable address information.")
            return
        
        if not session.get("surrounding_documents"):
            await websocket.send_text(f"I can generate Section 5.2.4 for {session['subject_address']}, but I need surrounding properties data first.")
            await websocket.send_text("Please upload PDFs containing surrounding property database listings, then ask me to generate Section 5.2.4 again.")
            return
        
        # Check if we have surrounding addresses
        if not session.get("surrounding_addresses"):
            await websocket.send_text(f"I have {len(session['surrounding_documents'])} surrounding property document(s), but I need the addresses for distance calculations.")
            await websocket.send_text("Please provide the addresses of the surrounding properties (one per message or comma-separated).")
            session["awaiting_addresses"] = True
            return
        
        # Both main and surrounding data available
        await websocket.send_text(f"Ready to generate Section 5.2.4 for {session['subject_address']}")
        await websocket.send_text(f"I have {len(session['surrounding_documents'])} surrounding property document(s)")
        await websocket.send_text("I need the groundwater flow direction (like 'northeast', 'SW', 'north', etc.)")
        session["awaiting_groundwater"] = True
        return
    
    # Handle address collection
    if session.get("awaiting_addresses"):
        # Parse addresses from user input
        addresses = [addr.strip() for addr in user_question.split(',')]
        # Clean and validate addresses
        addresses = [addr for addr in addresses if addr and len(addr) > 10]
        
        if addresses:
            session["surrounding_addresses"] = addresses
            session["awaiting_addresses"] = False
            await websocket.send_text(f"Received {len(addresses)} surrounding property addresses:")
            for addr in addresses:
                await websocket.send_text(f"  - {addr}")
            await websocket.send_text("Now I need the groundwater flow direction (like 'northeast', 'SW', 'north', etc.)")
            session["awaiting_groundwater"] = True
        else:
            await websocket.send_text("Please provide valid addresses. Example: '123 Main St, City, State' or provide multiple addresses separated by commas.")
        return
    
    # Check if user is providing groundwater flow direction
    if session.get("awaiting_groundwater"):
        groundwater_direction = extract_groundwater_direction(user_question)
        if groundwater_direction:
            await websocket.send_text(f"Using groundwater flow direction: {groundwater_direction}")
            await websocket.send_text("Calculating distances...")
            
            try:
                # Calculate distances
                raw_distance_data = tool_calculate_distances(session["subject_address"], session["surrounding_addresses"])
                await websocket.send_text(f"Calculated distances for {len(raw_distance_data['distances'])} properties")

                # Transform distance data into Claude-friendly format
                distance_data = {}
                for dist_info in raw_distance_data.get('distances', []):
                    address = dist_info['address']
                    distance_data[address] = {
                        'distance_feet': dist_info['distance_ft'],
                        'direction': dist_info['direction'],
                        'bearing_degrees': dist_info['bearing_deg']
                    }

                # Also include failed addresses for debugging
                if raw_distance_data.get('failed'):
                    await websocket.send_text(f"Failed to calculate distances for: {raw_distance_data['failed']}")
                
                # Combine all surrounding property data with ECHO enhancement
                combined_surrounding_data = ""
                combined_echo_summaries = ""
                
                for doc in session["surrounding_documents"]:
                    combined_surrounding_data += f"\n--- {doc['filename']} ---\n{doc['formatted']}\n"
                    
                    # Add ECHO summaries if available
                    if doc.get('echo_summary'):
                        combined_echo_summaries += f"\n--- ECHO Compliance Data for {doc['filename']} ---\n{doc['echo_summary']}\n"
                
                await websocket.send_text("Generating Section 5.2.4...")
                await websocket.send_text("--- Section 5.2.4 ---")
                
                # Generate enhanced Section 5.2.2 if we have ECHO data for surrounding properties
                if combined_echo_summaries.strip():
                    enhanced_context = f"""Surrounding Properties Environmental Database Data:
{combined_surrounding_data}

Enhanced EPA ECHO Compliance Summaries for Surrounding Properties:
{combined_echo_summaries}

Instructions: Generate Section 5.2.4 incorporating both the environmental database information and the enhanced EPA ECHO compliance summaries. When properties are mentioned as having ECHO database listings, enhance those entries with the detailed compliance information provided above. Integrate the ECHO compliance data seamlessly into the property summaries in the table format."""
                    
                    section_522 = await summarizer.generate_section_522_streaming(
                        websocket,
                        enhanced_context,
                        session["subject_address"],
                        groundwater_flow=groundwater_direction,
                        distance_data=distance_data,
                    )
                else:
                    # Standard Section 5.2.2 without ECHO enhancement
                    section_522 = await summarizer.generate_section_522_streaming(
                        websocket,
                        combined_surrounding_data,
                        session["subject_address"],
                        groundwater_flow=groundwater_direction,
                        distance_data=distance_data,
                    )
                
                session["section_522"] = section_522
                session["awaiting_groundwater"] = False
                
            except Exception as e:
                await websocket.send_text(f"Error generating Section 5.2.4: {str(e)}")
                session["awaiting_groundwater"] = False
        else:
            await websocket.send_text("I didn't recognize a groundwater flow direction. Please specify like: 'northeast', 'SW', 'north', 'southeast', etc.")
        return
    
    # Continue with existing intelligent chat logic for other questions
    # Include both main document and surrounding documents in context
    all_documents_context = f"Main Document ({session['main_document']['filename']}):\n{session['main_document']['formatted'][:2000]}"
    
    if session.get("surrounding_documents"):
        all_documents_context += "\n\nSurrounding Properties Documents:\n"
        for doc in session["surrounding_documents"]:
            all_documents_context += f"\n{doc['filename']}:\n{doc['formatted'][:1000]}"
    
    # Include ECHO summaries in context for Q&A
    echo_context = ""
    if session.get("main_document", {}).get("echo_summary"):
        echo_context += f"\n\nEnhanced ECHO Compliance Data for Main Property:\n{session['main_document']['echo_summary']}"
    
    for doc in session.get("surrounding_documents", []):
        if doc.get("echo_summary"):
            echo_context += f"\n\nEnhanced ECHO Compliance Data for {doc['filename']}:\n{doc['echo_summary']}"
    
    context = f"""
    You are an environmental assessment assistant. A user has uploaded and processed PDF documents.
    
    {all_documents_context}
    
    {echo_context}
    
    Generated Section 5.2.3:
    {session.get("section_523", "Not yet generated")}
    
    Subject Property Address: {session.get("subject_address", "Not extracted")}
    
    User Question: {user_question}
    
    Please answer the user's question based on this environmental assessment information. Be specific and reference the actual data from the documents.
    """
    
    try:
        # Use streaming method for intelligent chat
        ai_response = await summarizer.intelligent_chat_streaming(
            websocket,
            context,
            temperature=0.1,
            max_tokens=800
        )
        
    except Exception as e:
        await websocket.send_text(f"I had trouble processing your question: {str(e)}")