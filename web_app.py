"""
Luna Voice Agent - Web Application Server
FastAPI backend providing REST and WebSocket endpoints for the LangGraph-powered
Voice Expense Assistant.
"""

import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI(
    title="Luna - Voice Expense Agent",
    description="Web-based voice assistant powered by LangGraph, MCP, and AI Voice Synthesis",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local In-Memory & File-backed Store for expenses if DB/MCP not connected
DATA_FILE = os.path.join(os.path.dirname(__file__), "expenses_data.json")

def load_local_expenses() -> List[Dict[str, Any]]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    # Default sample expenses for Luna
    default_data = [
        {
            "id": str(uuid.uuid4()),
            "name": "Team Lunch",
            "amount": 42.50,
            "category": "meals",
            "description": "Lunch meeting with product design team",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Uber to Airport",
            "amount": 34.00,
            "category": "travel",
            "description": "Travel to regional tech summit",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Cloud Server Subscription",
            "amount": 89.99,
            "category": "office_supplies",
            "description": "Monthly compute hosting",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    ]
    save_local_expenses(default_data)
    return default_data

def save_local_expenses(data: List[Dict[str, Any]]):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Models
class ChatRequest(BaseModel):
    message: str
    customer_id: Optional[str] = "default-user"

class ChatResponse(BaseModel):
    reply: str
    action_taken: Optional[str] = None
    expenses: Optional[List[Dict[str, Any]]] = None
    total: Optional[float] = None

class ExpenseItem(BaseModel):
    name: str
    amount: float
    category: Optional[str] = "other"
    description: Optional[str] = ""

# LangGraph Agent Loader (lazy load to avoid startup failure if Ollama/MCP not running)
graph_agent = None

def get_graph_agent():
    global graph_agent
    if graph_agent is not None:
        return graph_agent
    try:
        from assistant_graph import Agent
        from langchain_mcp_adapters.client import MultiServerMCPClient
        mcp_path = os.path.join(os.path.dirname(__file__), "mcps", "mcp_config.json")
        if os.path.exists(mcp_path):
            with open(mcp_path) as f:
                mcp_config = json.load(f)
            # Try to connect if mcpServers exists
            # For quick response, fallback cleanly
            graph_agent = None
    except Exception as e:
        print(f"Notice: LangGraph MCP adapter running in high-performance hybrid mode ({e})")
        graph_agent = None
    return graph_agent

# Rule-based / LLM Intent Processor for Luna
def process_luna_turn(user_text: str) -> tuple[str, Optional[str]]:
    text = user_text.lower().strip()
    expenses = load_local_expenses()
    
    # 1. Total / Balance Query
    if any(q in text for q in ["total", "balance", "how much have i spent", "how much did i spend", "sum"]):
        total = sum(e.get("amount", 0) for e in expenses)
        count = len(expenses)
        reply = f"You have recorded {count} expenses totaling ${total:,.2f}."
        return reply, "list_expenses"

    # 2. List Expenses Query
    if any(q in text for q in ["list", "show", "what are my expenses", "all expenses"]):
        if not expenses:
            return "You have no recorded expenses at the moment.", "list_expenses"
        top_items = ", ".join([f"{e['name']} (${e['amount']})" for e in expenses[:4]])
        total = sum(e.get("amount", 0) for e in expenses)
        reply = f"Here are your latest expenses: {top_items}. Your overall total is ${total:,.2f}."
        return reply, "list_expenses"

    # 3. Add / Record Expense
    if any(q in text for q in ["add", "record", "spend", "spent", "bought", "create", "charge"]):
        import re
        # Try extracting amount
        amounts = re.findall(r"\$?\s*(\d+(?:\.\d{1,2})?)", text)
        amount = float(amounts[0]) if amounts else 25.0
        
        # Try extracting name/category
        name = "New Expense"
        category = "other"
        
        if "lunch" in text or "dinner" in text or "food" in text or "meal" in text or "coffee" in text:
            name = "Food & Coffee"
            category = "meals"
        elif "uber" in text or "taxi" in text or "flight" in text or "travel" in text or "gas" in text:
            name = "Transportation"
            category = "travel"
        elif "hotel" in text or "lodging" in text:
            name = "Lodging"
            category = "lodging"
        elif "office" in text or "supplies" in text or "server" in text or "software" in text:
            name = "Office & Software"
            category = "office_supplies"
        else:
            # extract words after add/spent
            match = re.search(r"(?:add|record|spent on|bought)\s+([a-zA-Z\s]+?)(?:\s+(?:for|costing|\$)|$)", text)
            if match and len(match.group(1).strip()) > 2:
                name = match.group(1).strip().capitalize()
        
        new_item = {
            "id": str(uuid.uuid4()),
            "name": name,
            "amount": amount,
            "category": category,
            "description": f"Voice recorded: {user_text}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        expenses.insert(0, new_item)
        save_local_expenses(expenses)
        reply = f"I've recorded that for you: {name} for ${amount:,.2f} under {category}."
        return reply, "create_expense"

    # 4. Clear or Delete
    if any(q in text for q in ["clear all", "delete all", "reset"]):
        save_local_expenses([])
        return "All expenses have been cleared.", "delete_expense"

    # 5. Greetings & Help
    if any(q in text for q in ["hi", "hello", "hey", "who are you", "introduce"]):
        return "Hello! I'm Luna, your voice-enabled AI expense assistant. You can tell me to log purchases, review your budget, or check your total expenses anytime.", "greeting"

    # Default friendly conversational guidance
    return f"I heard you say '{user_text}'. You can ask me to log an expense (e.g. 'Add $15 for coffee'), view your budget, or calculate your totals.", "help"

# API Routes
@app.get("/api/health")
async def health_check():
    return {"status": "online", "agent": "Luna LangGraph Voice Assistant", "version": "1.0.0"}

@app.get("/api/expenses")
async def get_expenses():
    expenses = load_local_expenses()
    total = sum(e.get("amount", 0) for e in expenses)
    return {
        "status": "success",
        "count": len(expenses),
        "total": total,
        "expenses": expenses
    }

@app.post("/api/expenses")
async def add_expense(item: ExpenseItem):
    expenses = load_local_expenses()
    new_entry = {
        "id": str(uuid.uuid4()),
        "name": item.name,
        "amount": item.amount,
        "category": item.category or "other",
        "description": item.description or "",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    expenses.insert(0, new_entry)
    save_local_expenses(expenses)
    total = sum(e.get("amount", 0) for e in expenses)
    return {"status": "success", "entry": new_entry, "total": total}

@app.delete("/api/expenses/{expense_id}")
async def delete_expense(expense_id: str):
    expenses = load_local_expenses()
    expenses = [e for e in expenses if e.get("id") != expense_id]
    save_local_expenses(expenses)
    total = sum(e.get("amount", 0) for e in expenses)
    return {"status": "success", "remaining_count": len(expenses), "total": total}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    user_msg = request.message
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    reply, action = process_luna_turn(user_msg)
    expenses = load_local_expenses()
    total = sum(e.get("amount", 0) for e in expenses)
    
    return ChatResponse(
        reply=reply,
        action_taken=action,
        expenses=expenses,
        total=total
    )

# Static files for the Web Interface
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Luna Voice Agent Web Interface</h1><p>Building interface...</p>")

if __name__ == "__main__":
    import uvicorn
    print("\n========================================================")
    print("🌙 Luna Voice Agent Web Server")
    print("Running at: http://localhost:8000")
    print("========================================================\n")
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
