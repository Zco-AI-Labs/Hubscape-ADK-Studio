import os
import json
import logging
import importlib.util
import sys
import webbrowser
from typing import List, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ADKSandbox")

# Load Mock Context
from . import mock_context
from .mock_context import HubscapeContext, get_adk_context

app = FastAPI(title="Hubscape ADK Studio - Local Sandbox")

# Enable CORS for easy local integration testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# App State for global tracking
app.state.mock_user = {
    "user_id": "dev-user-123",
    "name": "Dev Commander",
    "email": "dev@hubscape.com",
    "phone_number": "+15550199",
    "roles": ["member", "Hub Admin"],
    "hub_id": "dev-hub-abc",
    "org_id": "dev-org-xyz"
}
app.state.last_widget_payload = None

# Initialize settings state
app.state.settings = {
    "dev_gateway": os.getenv("HUBSCAPE_DEV_GATEWAY") == "true",
    "dev_pat": os.getenv("HUBSCAPE_DEV_PAT", ""),
    "dev_gateway_url": os.getenv("HUBSCAPE_DEV_GATEWAY_URL", "https://hubscape-b9558.web.app")
}

# Globals for the loaded agent
AGENT_CONFIG = {}
AGENT_LOGIC = None

# Dynamic Module Loading Helper
def load_local_module(module_name: str, file_path: str):
    if not os.path.exists(file_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        logger.info(f"Successfully loaded local module: {module_name}")
        return module
    except Exception as e:
        logger.error(f"❌ Error loading local module {module_name}: {e}")
        raise e

# Setup Agent on Startup
@app.on_event("startup")
def setup_agent():
    global AGENT_CONFIG, AGENT_LOGIC
    
    # Load config.json
    if not os.path.exists("config.json"):
        logger.error("❌ config.json not found! Place it in the root of the repository.")
        sys.exit(1)
        
    with open("config.json", "r") as f:
        AGENT_CONFIG = json.load(f)
        
    agent_id = AGENT_CONFIG.get("id", "todo_agent")
    logger.info(f"Loaded agent configuration for ID: '{agent_id}'")
    
    # Load logic.py
    if not os.path.exists("logic.py"):
        logger.error("❌ logic.py not found! Place it in the root of the repository.")
        sys.exit(1)
    AGENT_LOGIC = load_local_module("logic", "logic.py")
    
    # Mount api.py router if present
    if os.path.exists("api.py"):
        agent_api = load_local_module("api", "api.py")
        if agent_api and hasattr(agent_api, "router"):
            app.include_router(agent_api.router, prefix=f"/api/plugins/{agent_id}")
            logger.info(f"🔌 Mounted custom API router at: /api/plugins/{agent_id}/")

# Request Models
class ChatMessage(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []

class TriggerToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}

# Mock LLM fallback when API key is missing
def mock_llm_response(message: str) -> Dict[str, Any]:
    msg_lower = message.lower()
    if "list" in msg_lower or "show" in msg_lower or "tasks" in msg_lower:
        return {
            "type": "tool_call",
            "name": "list_tasks",
            "args": {}
        }
    elif "add" in msg_lower or "create" in msg_lower or "new" in msg_lower:
        title = message.replace("add", "").replace("task", "").replace("create", "").strip(" :.,'\"")
        priority = "high" if "high" in msg_lower else "low" if "low" in msg_lower else "medium"
        return {
            "type": "tool_call",
            "name": "add_task",
            "args": {"title": title or "New Sandbox Task", "priority": priority}
        }
    return {
        "type": "text",
        "text": f"🤖 [Sandbox Holodeck Mode]: I heard you say: '{message}'. Set a GEMINI_API_KEY environment variable to test true AI chat orchestration! Or use the Right Panel to execute specific tools."
    }

# Execute Local Tool Logic
async def run_tool(name: str, args: dict, context: HubscapeContext) -> dict:
    if not AGENT_LOGIC:
        return {"error": "Agent logic not loaded."}
        
    if not hasattr(AGENT_LOGIC, name):
        return {"error": f"Tool function '{name}' not found in logic.py."}
        
    func = getattr(AGENT_LOGIC, name)
    try:
        logger.info(f"🔌 Executing tool: '{name}' with args: {args}")
        result = await func(context, args)
        return result
    except Exception as e:
        logger.error(f"💥 Exception in tool '{name}': {e}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}

# Chat API Router
@app.post("/api/chat")
async def chat(payload: ChatMessage, context: HubscapeContext = Depends(get_adk_context)):
    api_key = os.environ.get("GEMINI_API_KEY")
    user_msg = payload.message
    agent_id = AGENT_CONFIG.get("id", "todo_agent")
    
    if not api_key:
        # Fallback to Mock / Rules Engine
        decision = mock_llm_response(user_msg)
        if decision["type"] == "text":
            return {
                "response": decision["text"],
                "history": payload.history + [{"role": "user", "content": user_msg}, {"role": "model", "content": decision["text"]}],
                "widgetPayload": None,
                "trace": {
                    "query": user_msg,
                    "agent_id": agent_id,
                    "mode": "Offline Mock (No API Key)",
                    "steps": [
                        {"name": "User Input", "detail": user_msg, "status": "success"},
                        {"name": "Mock Router", "detail": "No tool call matched. Returned static response.", "status": "success"}
                    ]
                }
            }
        else:
            # Execute tool directly
            tool_name = decision["name"]
            tool_args = decision["args"]
            
            steps = [
                {"name": "User Input", "detail": user_msg, "status": "success"},
                {"name": "Mock Router", "detail": f"Matched pattern to tool '{tool_name}'", "status": "success"},
                {"name": f"Run Tool: {tool_name}", "detail": f"Args: {json.dumps(tool_args)}", "status": "running"}
            ]
            
            tool_result = await run_tool(tool_name, tool_args, context)
            
            status = "error" if "error" in tool_result else "success"
            steps[-1]["status"] = status
            steps[-1]["detail"] = f"Result: {json.dumps(tool_result)[:80]}..."
            
            summary = f"Executed tool '{tool_name}' successfully."
            if "message" in tool_result:
                summary = tool_result["message"]
            elif "error" in tool_result:
                summary = f"Tool failed: {tool_result['error']}"
                
            if context._widget_payload:
                steps.append({"name": "Render Widget", "detail": f"Widget ID: {context._widget_payload.get('widgetId')}", "status": "success"})
                
            return {
                "response": f"🤖 [Manual Router]: Calling tool `{tool_name}({json.dumps(tool_args)})` -> Result: {summary}",
                "history": payload.history + [{"role": "user", "content": user_msg}, {"role": "model", "content": summary}],
                "widgetPayload": context._widget_payload,
                "trace": {
                    "query": user_msg,
                    "agent_id": agent_id,
                    "mode": "Offline Mock (No API Key)",
                    "steps": steps
                }
            }

    # If GEMINI_API_KEY is present, we run a real Gemini LLM orchestration loop
    if api_key:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            logger.warning("⚠️ 'google-genai' package is not installed in this environment. Falling back to offline Mock Mode.")
            api_key = None

    if not api_key:
        # Fallback to Mock / Rules Engine
        decision = mock_llm_response(user_msg)
        if decision["type"] == "text":
            return {
                "response": decision["text"],
                "history": payload.history + [{"role": "user", "content": user_msg}, {"role": "model", "content": decision["text"]}],
                "widgetPayload": None,
                "trace": {
                    "query": user_msg,
                    "agent_id": agent_id,
                    "mode": "Offline Mock (Import Fallback)",
                    "steps": [
                        {"name": "User Input", "detail": user_msg, "status": "success"},
                        {"name": "Mock Router", "detail": "google-genai missing. Returned static mock response.", "status": "success"}
                    ]
                }
            }
        else:
            tool_name = decision["name"]
            tool_args = decision["args"]
            steps = [
                {"name": "User Input", "detail": user_msg, "status": "success"},
                {"name": "Mock Router", "detail": "google-genai missing. Routing mock tool call.", "status": "success"},
                {"name": f"Run Tool: {tool_name}", "detail": f"Args: {json.dumps(tool_args)}", "status": "running"}
            ]
            tool_result = await run_tool(tool_name, tool_args, context)
            status = "error" if "error" in tool_result else "success"
            steps[-1]["status"] = status
            steps[-1]["detail"] = f"Result: {json.dumps(tool_result)[:80]}..."
            
            summary = f"Executed tool '{tool_name}' successfully."
            if "message" in tool_result:
                summary = tool_result["message"]
            elif "error" in tool_result:
                summary = f"Tool failed: {tool_result['error']}"
                
            if context._widget_payload:
                steps.append({"name": "Render Widget", "detail": f"Widget ID: {context._widget_payload.get('widgetId')}", "status": "success"})
                
            return {
                "response": f"🤖 [Manual Router]: Calling tool `{tool_name}({json.dumps(tool_args)})` -> Result: {summary}",
                "history": payload.history + [{"role": "user", "content": user_msg}, {"role": "model", "content": summary}],
                "widgetPayload": context._widget_payload,
                "trace": {
                    "query": user_msg,
                    "agent_id": agent_id,
                    "mode": "Offline Mock (Import Fallback)",
                    "steps": steps
                }
            }

    try:
        # Initialize Google GenAI client
        client = genai.Client(api_key=api_key)
        
        # Convert config tools into Google GenAI Tool models
        genai_tools = []
        for t in AGENT_CONFIG.get("tools", []):
            params_dict = t.get("parameters", {})
            properties = {}
            for k, prop in params_dict.get("properties", {}).items():
                prop_type = prop.get("type", "STRING")
                properties[k] = types.Schema(
                    type=types.Type[prop_type],
                    description=prop.get("description", "")
                )
            
            schema = types.Schema(
                type=types.Type.OBJECT,
                properties=properties,
                required=params_dict.get("required", [])
            )
            
            genai_tools.append(
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=schema
                )
            )
        
        config = types.GenerateContentConfig(
            system_instruction=AGENT_CONFIG.get("system_prompt", ""),
            tools=[types.Tool(function_declarations=genai_tools)] if genai_tools else None,
            temperature=0.7
        )

        # Assemble conversation history format
        contents = []
        for h in payload.history:
            role = "user" if h["role"] == "user" else "model"
            # Protect against empty content or special mock logs
            part_content = h.get("content", "")
            if part_content.startswith("[Tool calls"):
                continue
            contents.append(types.Content(role=role, parts=[types.Part.from_text(part_content)]))
        
        contents.append(types.Content(role="user", parts=[types.Part.from_text(user_msg)]))
        
        steps = [
            {"name": "User Input", "detail": user_msg, "status": "success"},
            {"name": "Platform Host", "detail": f"Booted agent '{agent_id}' system prompt.", "status": "success"}
        ]
        
        # Call Gemini model
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=config
        )
        
        history_out = payload.history + [{"role": "user", "content": user_msg}]
        
        # Handle function calls in a loop (up to 3 iterations for tool chaining)
        for _ in range(3):
            if not response.function_calls:
                break
                
            tool_calls = response.function_calls
            history_out.append({"role": "model", "content": f"[Tool calls requested: {len(tool_calls)}]"})
            
            tool_parts = []
            for call in tool_calls:
                steps.append({"name": f"Tool Called: {call.name}", "detail": f"Args: {json.dumps(dict(call.args))}", "status": "running"})
                
                # Run the logic tool
                result = await run_tool(call.name, dict(call.args), context)
                
                status = "error" if "error" in result else "success"
                steps[-1]["status"] = status
                steps[-1]["detail"] = f"Output: {json.dumps(result)[:80]}..."
                
                tool_parts.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={"result": result}
                    )
                )
                
            # Feed the tool results back into Gemini
            contents.append(response.candidates[0].content)
            contents.append(types.Content(role="tool", parts=tool_parts))
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=config
            )
            
        final_text = response.text or "[Visual Update Rendered]"
        history_out.append({"role": "model", "content": final_text})
        steps.append({"name": "Agent Response", "detail": final_text[:80], "status": "success"})
        
        if context._widget_payload:
            steps.append({"name": "Render Widget", "detail": f"Widget ID: {context._widget_payload.get('widgetId')}", "status": "success"})
            
        return {
            "response": final_text,
            "history": history_out,
            "widgetPayload": context._widget_payload,
            "trace": {
                "query": user_msg,
                "agent_id": agent_id,
                "mode": "Live Gemini Orchestrator",
                "steps": steps
            }
        }
        
    except Exception as e:
        logger.error(f"GenAI Loop failure: {e}", exc_info=True)
        return {
            "response": f"⚠️ Gemini LLM Call Failed: {str(e)}. Falling back to offline Mock Router.",
            "history": payload.history + [{"role": "user", "content": user_msg}, {"role": "model", "content": "Gemini API error."}],
            "widgetPayload": None,
            "trace": {
                "query": user_msg,
                "agent_id": agent_id,
                "mode": "Fallback Router",
                "steps": [
                    {"name": "User Input", "detail": user_msg, "status": "success"},
                    {"name": "Gemini API Call", "detail": f"Failed: {str(e)}", "status": "error"}
                ]
            }
        }

# Trigger Tool Manually Endpoint
@app.post("/api/sandbox/trigger-tool")
async def trigger_tool(payload: TriggerToolRequest, context: HubscapeContext = Depends(get_adk_context)):
    result = await run_tool(payload.tool_name, payload.arguments, context)
    return {
        "status": "success",
        "result": result,
        "widgetPayload": context._widget_payload
    }

# Update User Info in Sandbox
@app.post("/api/sandbox/user")
async def update_user(req_body: dict):
    app.state.mock_user.update(req_body)
    return {"status": "success", "user": app.state.mock_user}

@app.get("/api/sandbox/user")
async def get_user():
    return app.state.mock_user

# Get Settings in Sandbox
@app.get("/api/sandbox/settings")
async def get_settings():
    return app.state.settings

# Update Settings in Sandbox
@app.post("/api/sandbox/settings")
async def update_settings(req_body: dict):
    app.state.settings.update(req_body)
    return {"status": "success", "settings": app.state.settings}

# Serve Holodeck Static Files
@app.get("/", response_class=HTMLResponse)
async def serve_home():
    holodeck_index = os.path.join(PACKAGE_DIR, "holodeck", "index.html")
    if os.path.exists(holodeck_index):
        with open(holodeck_index, "r") as f:
            return f.read()
    return "<h3>Holodeck Frontend files are missing. Make sure holodeck/index.html is created!</h3>"

# If holodeck folder exists in the package folder, mount it for static assets
holodeck_dir = os.path.join(PACKAGE_DIR, "holodeck")
if os.path.exists(holodeck_dir):
    app.mount("/holodeck", StaticFiles(directory=holodeck_dir), name="holodeck")

def main():
    # Automatically open local browser tab
    try:
        webbrowser.open("http://localhost:8090")
    except Exception:
        pass
    uvicorn.run("hubscape_adk.run_sandbox:app", host="0.0.0.0", port=8090, reload=True)

if __name__ == "__main__":
    main()
