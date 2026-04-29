# 🌙 Luna: LangGraph Voice Agent - Complete Source Guide

This document provides a comprehensive overview of the **Luna** voice-enable expense manager. It is designed to be read from top to bottom to understand how each component interacts to create a seamless voice-to-tool experience.

---

## 🏗️ Architecture Overview

Luna is built on a **Modular AI Agent** architecture:

1.  **Voice Layer (`voice_utils.py`)**: Handles the "Senses" (Hearing and Speaking). Uses Whisper for transcription and Edge-TTS for voice.
2.  **Brain Layer (`assistant_graph.py`)**: Orchestrates the logic using **LangGraph**. It decides when to speak and when to call tools.
3.  **Tool Layer (`mcps/local_servers/db.py`)**: A set of standalone database operations exposed via **MCP (Model Context Protocol)**.
4.  **Loop Layer (`main.py`)**: Connects the senses to the brain in a continuous conversational loop.

---

## 📚 Understanding the Code (Recommended Sequence)

1.  **`state.py`**: Understand what information the agent "remembers" between turns.
2.  **`mcps/local_servers/db.py`**: See the tools available to the agent (Create, List, Update, etc.).
3.  **`assistant_graph.py`**: See how the agent is structured as a state machine.
4.  **`voice_utils.py`**: Learn how audio is processed and noise is filtered.
5.  **`main.py`**: See how it all comes together.

---

## 💻 Full Source Code

### 1. Project Configuration & Database
#### `pyproject.toml`
Defines the environment and dependencies.
```toml
[project]
name = "langgraph-voice-agent"
version = "0.1.0"
description = "A voice-enabled expense manager using LangGraph and MCP."
authors = [{ name = "Admin", email = "admin@example.com" }]
dependencies = [
    "langgraph",
    "langchain-ollama",
    "sqlalchemy",
    "mcp",
    "openai-whisper",
    "edge-tts",
    "pygame",
    "pydub",
    "sounddevice",
    "pynput",
    "scipy",
    "pandas",
    "python-dotenv",
]

[tool.setuptools]
packages = ["mcps", "mcps.local_servers"]
```

#### `.env`
*Note: Create this file and add your Supabase URI.*
```bash
SUPABASE_URI=postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:6543/postgres
```

#### `generate_tables.sql`
The foundation of the database.
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS expenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL DEFAULT 'other',
    amount DOUBLE PRECISION NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE
);
```

---

### 2. The Agent State
#### `state.py`
Defines the memory structure (messages and context).
```python
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # 'add_messages' ensures new messages are appended to the history
    messages: Annotated[Sequence[BaseMessage], add_messages]
    customer_id: str
```

---

### 3. The Tools (MCP Server)
#### `mcps/local_servers/db.py`
Standalone tools that manage the database.
```python
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import List, Optional
from sqlalchemy import ForeignKey, String, text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, sessionmaker
from uuid import UUID, uuid4
from datetime import datetime
import os
from pydantic import BaseModel
from enum import Enum

load_dotenv()

# --- Database Setup ---
engine = create_engine(url=os.getenv("SUPABASE_URI"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase): pass

class DBExpense(Base):
    __tablename__ = "expenses"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'other'"))
    amount: Mapped[float] = mapped_column(nullable=False)
    customer_id: Mapped[UUID] = mapped_column(nullable=False)

class ExpenseCategory(str, Enum):
    MEALS = "meals"
    TRAVEL = "travel"
    LODGING = "lodging"
    OFFICE_SUPPLIES = "office_supplies"
    OTHER = "other"

class Expense(BaseModel):
    id: UUID
    name: str
    category: ExpenseCategory
    amount: float
    customer_id: UUID

# --- MCP Tools ---
mcp = FastMCP("db")

@mcp.tool()
async def create_expense(customer_id: UUID, name: str, amount: float, category: ExpenseCategory) -> str:
    """Create a NEW expense."""
    with SessionLocal() as session:
        new_exp = DBExpense(name=name, amount=amount, category=category.value, customer_id=customer_id)
        session.add(new_exp)
        session.commit()
    return f"✅ Created: {name} (${amount})"

@mcp.tool()
async def list_expenses(customer_id: UUID) -> str:
    """List actual expenses for a customer."""
    with SessionLocal() as session:
        expenses = session.query(DBExpense).filter(DBExpense.customer_id == customer_id).all()
        if not expenses: return "No expenses found."
        return "\n".join([f"- {e.name}: ${e.amount} ({e.category})" for e in expenses])

@mcp.tool()
async def update_expense(expense_id: UUID, amount: Optional[float] = None) -> str:
    """Update an existing expense amount."""
    with SessionLocal() as session:
        exp = session.query(DBExpense).get(expense_id)
        if exp:
            if amount is not None: exp.amount = amount
            session.commit()
            return "✅ Updated."
        return "❌ Not found."

@mcp.tool()
async def delete_all_expenses(customer_id: UUID) -> str:
    """Clear the database for a customer."""
    with SessionLocal() as session:
        session.query(DBExpense).filter(DBExpense.customer_id == customer_id).delete()
        session.commit()
    return "✅ Database cleared."

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

### 4. The Brain (LangGraph)
#### `assistant_graph.py`
Determines the flow of conversation. Includes grounding to prevent hallucinations.
```python
from langgraph.graph import StateComponents, StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_ollama import ChatOllama
from state import AgentState

class Agent:
    def __init__(self, tools):
        self.tools = tools
        # We use a strict system prompt to prevent the model from guessing data
        self.system_prompt = """You are Luna, a voice expense manager.
        RULES:
        - If 'list_expenses' is empty: say "Database is empty." DO NOT invent data.
        - If input is noise/gibberish: ask for clarification.
        - Categorize as 'meals', 'travel', 'lodging', 'office_supplies', or 'other'.
        - Use tool-calling for all DB actions."""
        
        self.llm = ChatOllama(model="llama3.1").bind_tools(tools=self.tools)
        self.builder = StateGraph(AgentState)
        self._build_graph()
        self.graph = self.builder.compile()

    def _call_model(self, state: AgentState):
        msgs = [{"role": "system", "content": self.system_prompt}] + state["messages"]
        response = self.llm.invoke(msgs)
        return {"messages": [response]}

    def _build_graph(self):
        self.builder.add_node("assistant", self._call_model)
        self.builder.add_node("tools", ToolNode(self.tools))
        
        self.builder.add_edge(START, "assistant")
        self.builder.add_conditional_edges("assistant", tools_condition)
        self.builder.add_edge("tools", "assistant")
```

---

### 5. The Senses (Voice Utilities)
#### `voice_utils.py`
The bridge between sound and text. Includes the 'S' key skip logic.
```python
import whisper, edge_tts, pygame, tempfile, os, asyncio, sys, termios, tty, select
import numpy as np
from scipy.io.wavfile import write

# Load Whisper model once
stt_model = whisper.load_model("medium")

async def record_audio_until_stop():
    """Records until Enter is pressed. Filters silent hum/noise."""
    import sounddevice as sd
    sample_rate = 16000
    audio_data = []
    recording = True

    def callback(indata, frames, time, status):
        if recording: audio_data.append(indata.copy())
        
    print("\n[Recording... Press Enter to stop]")
    with sd.InputStream(samplerate=sample_rate, channels=1, callback=callback):
        await asyncio.get_running_loop().run_in_executor(None, input)
        recording = False

    audio_np = np.concatenate(audio_data, axis=0)
    rms = np.sqrt(np.mean(audio_np**2))
    if rms < 0.005: # Noise floor
        print("🔇 Silence detected.")
        return ""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        write(tmp.name, sample_rate, (audio_np * 32768).astype(np.int16))
        result = stt_model.transcribe(tmp.name, language="en")
        os.unlink(tmp.name)
    return result["text"].strip()

async def play_audio(message: str):
    """Plays voice. Press 'S' to skip instantly."""
    cleaned = message.replace("**", "")
    print(f"\n🗣️ Luna: {cleaned}\n(Press 's' to skip)")
    
    comm = edge_tts.Communicate(cleaned, "en-US-AvaNeural")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        await comm.save(tmp.name)
        
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(tmp.name)
            pygame.mixer.music.play()
            tty.setcbreak(fd) # Non-blocking key detection
            while pygame.mixer.music.get_busy():
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    if sys.stdin.read(1).lower() == 's':
                        pygame.mixer.music.stop()
                        print("[Skipped]")
                        break
                await asyncio.sleep(0.05)
            pygame.mixer.quit()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            os.unlink(tmp.name)
```

---

### 6. The Heart (Main Loop)
#### `main.py`
The final assembly of all parts.
```python
import asyncio, json
from state import AgentState
from voice_utils import record_audio_until_stop, play_audio
from assistant_graph import Agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.messages import HumanMessage, AIMessage

async def main():
    customer_id = "6e1a6130-5be4-4778-92a9-b86dc5f16750"
    
    with open("mcps/mcp_config.json") as f:
        config = json.load(f)
    
    client = MultiServerMCPClient(connections=config["mcpServers"])
    tools = await client.get_tools()
    agent = Agent(tools=tools)
    
    # Starting Greeting
    state = AgentState(messages=[HumanMessage(content="Hello Luna")], customer_id=customer_id)

    while True:
        # Run AI Brain
        result = await agent.graph.ainvoke(state)
        last_msg = result["messages"][-1]
        
        # Senses: Speaking
        if isinstance(last_msg, AIMessage):
            await play_audio(last_msg.content)
            
        # Senses: Hearing
        text = await record_audio_until_stop()
        if any(w in text.lower() for w in ["exit", "quit", "goodbye"]):
            print("👋 Bye!")
            break
            
        # Update memory
        state = result
        state["messages"].append(HumanMessage(content=text))

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🏁 How to Run
1.  Ensure **Ollama** is running with `llama3.1`.
2.  Install dependencies: `pip install -r requirements.txt`. (Note: Manual installs like `pygame`, `pynput`, `sounddevice` are required).
3.  Set your `SUPABASE_URI` in `.env`.
4.  Run `python main.py`.

Luna is now fully documented for your study and expansion! 🌙
