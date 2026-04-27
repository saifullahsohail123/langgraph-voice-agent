import json
import asyncio
import logging
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk
from langchain_mcp_adapters.client import MultiServerMCPClient
from state import AgentState
from voice_utils import record_audio_until_stop, play_audio
from assistant_graph import Agent

with open("mcps/mcp_config.json") as f:
    mcp_config = json.load(f)

async def stream_graph_response(input_state: AgentState, agent_graph, config: dict):
    """Stream the response from the graph."""
    async for chunk, metadata in agent_graph.astream(
        input=input_state, 
        stream_mode="messages", 
        config=config
    ):
        if isinstance(chunk, AIMessageChunk):
            print(chunk.content, end="", flush=True)

async def main():
    config = {"configurable": {"thread_id": "thread-1"}}
    # Example customer ID (you can change this to a real one from your DB)
    customer_id = "6e1a6130-5be4-4778-92a9-b86dc5f16750"

    print("Initializing MultiServerMCPClient...")
    client = MultiServerMCPClient(connections=mcp_config["mcpServers"])
    
    tools = await client.get_tools()
    print(f"Loaded {len(tools)} tools from MCP.")

    agent_graph = Agent(tools=tools).graph

        # Initial turn
    initial_input = AgentState(
            messages=[HumanMessage(content="Briefly introduce yourself and ask how you can help today.")],
            customer_id=customer_id
        )

    while True:
            print("\n ---- Assistant ---- \n")
            await stream_graph_response(initial_input, agent_graph, config)
            
            # Get latest state to find final response
            state = agent_graph.get_state(config)
            last_msg = state.values["messages"][-1]
            
            if isinstance(last_msg, AIMessage):
                await play_audio(last_msg.content)

            # Record user voice
            user_input = await record_audio_until_stop()
            if not user_input:
                continue
                
            if any(word in user_input.lower() for word in ["exit", "quit", "goodbye"]):
                print("👋 Gracefully exiting. Have a great day!")
                break
                
            # Add user message to state for next turn
            initial_input = AgentState(
                messages=[HumanMessage(content=user_input)],
                customer_id=customer_id
            )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")