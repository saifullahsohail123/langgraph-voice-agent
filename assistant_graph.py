from langchain_core.messages import SystemMessage
# from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from state import AgentState
from mcps.local_servers.db import ExpenseCategory

class Agent:
    def __init__(self, tools, name="Luna", model="llama3.1"):
        self.system_prompt = """You are Luna, a helpful voice-based expense manager.
        
        How to handle the user's request:
        - If the user's request is nonsensical, gibberish, or unclear: Ask "I'm sorry, I didn't catch that. Could you repeat it?". NEVER try to guess an expense from gibberish.
        - For general conversation: Respond with brief plain text.
        - To record an expense: You MUST have both a 'name' and 'amount'. If either is missing, ASK for it. NEVER hallucinate details.
        - Once you have both 'name' and 'amount', use 'create_expense'.

        Categories for expenses: {expense_categories}
        The active customer_id is: {customer_id}
        
        Keep responses brief and friendly."""
        self.tools = tools
        # self.llm = ChatGoogleGenerativeAI(model=model).bind_tools(tools=self.tools)
        self.llm = ChatOllama(model=model).bind_tools(tools=self.tools)
        self.graph = self.build_graph()

    def build_graph(self):
        builder = StateGraph(AgentState)

        def assistant(state: AgentState):
            system_prompt = self.system_prompt.format(
                customer_id=state.customer_id,
                expense_categories=", ".join([c.value for c in ExpenseCategory])
            )
            response = self.llm.invoke([SystemMessage(content=system_prompt)] + state.messages)
            state.messages.append(response)
            return state

        builder.add_node(assistant)
        builder.add_node(ToolNode(self.tools))
        
        builder.set_entry_point("assistant")
        builder.add_conditional_edges("assistant", tools_condition)
        builder.add_edge("tools", "assistant")

        return builder.compile(checkpointer=InMemorySaver())