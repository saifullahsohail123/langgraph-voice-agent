from langchain_core.messages import SystemMessage
# from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from state import AgentState

class Agent:
    def __init__(self, tools, name="Luna", model="llama3"):
        self.system_prompt = "You are Luna, the company's expense manager..."
        self.tools = tools
        # self.llm = ChatGoogleGenerativeAI(model=model).bind_tools(tools=self.tools)
        self.llm = ChatOllama(model=model).bind_tools(tools=self.tools)
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