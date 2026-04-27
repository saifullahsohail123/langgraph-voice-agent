# Building a LangGraph Voice Agent: Step-by-Step Tutorial

Welcome! In this tutorial, we will build a voice-enabled AI assistant named **Luna** that can manage expenses through natural conversation. We'll utilize LangGraph for orchestrating the agent, Google's Gemini LLM (or OpenAI, depending on your API choice), and Model Context Protocol (MCP) to seamlessly connect our agent to a database.

You will learn how to set up the project from scratch, implement an MCP tool server for Python database operations, build the LangGraph orchestration loop, and tie it into asynchronous audio recording.

Let's get started!

---

## 🏗 Project Architecture
Before digging into the code, here is how the application is structured:

1. **`main.py`**: The application entry point. It handles user interactions, manages the conversation loop, hooks into audio/voice, and yields intermediate outputs from LangGraph.
2. **`state.py`**: Defines the shared state schema for LangGraph.
3. **`assistant_graph.py`**: Constructs the LangGraph orchestration. It instantiates the Google Gemini model and defines the `ToolNode`.
4. **`voice_utils.py`**: Implements audio input via PyAudio/sounddevice and audio playback.
5. **`mcps/`**: A subdirectory managing the MCP configuration and the local `FastMCP` database server (`mcps/local_servers/db.py`).

---

## Step 1: Initial Setup & Dependencies

First, let's create a new standard python environment in your repository root (`/home/admin1/Desktop/Self Learning/langraph-voice-agent`) and install all required dependencies.

**Create the `pyproject.toml` file**:
```toml
[project]
name = "langgraph-voice-agent"
version = "0.1.0"
description = "Voice enabled langgraph agent."
requires-python = ">=3.10"
dependencies = [
    "langchain-mcp-adapters>=0.1.1",
    "langchain-openai>=0.3.17",
    "langchain-google-genai>=2.0.0",
    "langgraph>=0.4.5",
    "mcp>=1.9.0",
    "pandas>=2.2.3",
    "psycopg2-binary>=2.9.10",
    "pydantic>=2.11.4",
    "python-dotenv>=1.1.0",
    "scipy>=1.15.3",
    "sounddevice>=0.5.2",
    "sqlalchemy>=2.0.41",
]
```
*(Tip: Install dependencies using standard `pip install -e .` or your favorite package manager like `uv sync`)*

Create a `.env` file in the root with:
```env
OPENAI_API_KEY=your_openai_api_key
SUPABASE_URI=postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxx.supabase.co:5432/postgres
```

### 💡 How to get your `SUPABASE_URI`
1. **Login** to your [Supabase Dashboard](https://supabase.com/dashboard).
2. **Select your project** (or create a new one).
3. Click on the **Settings** (gear icon) in the bottom-left sidebar.
4. Go to the **Database** tab.
5. Scroll down to the **Connection string** section.
6. Select the **URI** tab.
7. **Copy the URI**. It will look something like: `postgresql://postgres:[YOUR-PASSWORD]@db.vnoqyv...supabase.co:5432/postgres`.
8. **Important**: Replace `[YOUR-PASSWORD]` with the password you set when creating the project.

---

## Step 2: Database and MCP Server Setup

Model Context Protocol (MCP) creates a generic bridge to database operations. We'll use `FastMCP` alongside SQLAlchemy.

**1. Create a Configuration File**
Create a file at `mcps/mcp_config.json`:
```json
{
    "mcpServers": {
        "db": {
            "command": "python",
            "args": [
                "./mcps/local_servers/db.py"
            ],
            "transport": "stdio"
        }
    }
}
```

**2. Implement `db.py` Server**
Create a file at `mcps/local_servers/db.py`. In this file, define:
* **SQLAlchemy Models** for `DBCustomer` and `DBExpense`.
* **Pydantic Types** like `Customer` and `Expense` + `ExpenseCategory` Enum.
* **FastMCP Tool bindings**: Decorate database interaction async functions with `@mcp.tool()`.

*Example outline of `mcps/local_servers/db.py`:*
```python
import os
from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# ... import models ...

# Initialize Engine
engine = create_engine(url=os.getenv("SUPABASE_URI"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

mcp = FastMCP("db")

@mcp.tool()
async def create_expense(customer_id, name, amount, category, description) -> str:
    # SQLAlchemy logic here...
    return "Expense JSON string"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

## Step 3: Graph State and Models

Next, establish what state is passed between LangGraph nodes during each turn of the conversation.

**Create `state.py`**:
```python
from langgraph.graph import add_messages
from pydantic import BaseModel
from typing import Annotated, List

class AgentState(BaseModel):
    messages: Annotated[List, add_messages] = []
    customer_id: str = ""
```
This is a standard LangGraph state leveraging `add_messages` to maintain conversation history.

---

## Step 4: The Assistant Graph

Now we design the mental orchestration loop of the agent.

**Create `assistant_graph.py`**:
```python
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from state import AgentState

class Agent:
    def __init__(self, tools, name="Luna", model="gemini-2.5-flash-preview-native-audio-dialog"):
        self.system_prompt = "You are Luna, the company's expense manager..."
        self.tools = tools
        self.llm = ChatGoogleGenerativeAI(model=model).bind_tools(tools=self.tools)
        self.graph = self.build_graph()

    def build_graph(self):
        builder = StateGraph(AgentState)

        def assistant(state: AgentState):
            system_prompt = self.system_prompt.format(customer_id=state.customer_id)
            response = self.llm.invoke([SystemMessage(content=system_prompt)] + state.messages)
            state.messages.append(response)
            return state

        builder.add_node(assistant)
        builder.add_node(ToolNode(self.tools))
        
        builder.set_entry_point("assistant")
        builder.add_conditional_edges("assistant", tools_condition)
        builder.add_edge("tools", "assistant")

        return builder.compile(checkpointer=InMemorySaver())
```
*Note exactly how nodes are added to `builder` and how `tools_condition` routes to the tool node if the LLM requests a tool.*

---

## Step 5: Voice Utilities

The agent needs to “speak” and “hear.” 

**Create `voice_utils.py`**:
In this file, utilize `sounddevice` and `asyncio` to read microphone input buffers until a user hits Enter, convert it to a WAV buffer stream using `scipy.io.wavfile`, and hit a Speech-to-Text provider or just mock string returns for early testing (since native multimodal is under active development, we often fall back to strings).

```python
import sounddevice as sd
import numpy as np
import asyncio

async def record_audio_until_stop():
    # Recording inner loop ... 
    return "Dummy transcribed text or actual google API call"

async def play_audio(message: str):
    # Pass clean text message to a TTS engine or just print
    print("\n🗣️ (Simulated Speech Playback):", message)
```

---

## Step 6: Putting It All Together in `main.py`

This will inject the multi-server MCP client to grab the dynamically hosted tools and start the LangGraph inference loop.

**Create `main.py`**:
```python
import json
import asyncio
from langchain_core.messages import HumanMessage, AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from state import AgentState
from voice_utils import record_audio_until_stop, play_audio
from assistant_graph import Agent

with open("mcps/mcp_config.json") as f:
    mcp_config = json.load(f)

async def main():
    config = {"configurable": {"thread_id": "thread-1"}}
    customer_id = "your-sample-uuid"

    # 1. Fetch MCP tools
    client = MultiServerMCPClient(connections=mcp_config["mcpServers"])
    tools = await client.get_tools()

    # 2. Initalize agent with those tools
    agent_graph = Agent(tools=tools).build_graph()

    # 3. Initial input
    initial_input = AgentState(
        messages=[HumanMessage(content="Introduce yourself.")],
        customer_id=customer_id
    )

    transcribed_text = ""
    while True:
        # LangGraph chunk streaming logic 
        async for chunk, metadata in agent_graph.astream(initial_input, stream_mode="messages", config=config):
            # Print response progressively ...
            pass
            
        # Get final state & play back audio
        thread_state = agent_graph.get_state(config=config)
        last_message = thread_state.values.get("messages")[-1]
        if isinstance(last_message, AIMessage):
            await play_audio(last_message.content)

        # Await human Input via Voice Utils
        transcribed_text = await record_audio_until_stop()
        if "exit" in transcribed_text.lower():
            break
        initial_input.messages.append(HumanMessage(content=transcribed_text))

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Final Review
You have successfully wired a robust voice-agent capable of updating your personal finance Postgres DB completely through conversational interfaces! 

**To Start:**
1. Run `uv sync` or `pip install -e .` to setup dependencies.
2. Initialize database context (run your supabase scripts to bootstrap schema).
3. `python main.py` and start speaking into your mic!
