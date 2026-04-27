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