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
        self.system_prompt = """You are Luna, the company's expense manager.
        
        CRITICAL RULES:
        1. Only use the 'create_expense' tool when the user EXPLICITLY provides a name and a monetary amount.
        2. NEVER make up (hallucinate) an amount. If the user says "I spent money on lunch" but doesn't say how much, YOU MUST ASK "How much did you spend on lunch?".
        3. Use the built-in tool-calling feature. NEVER output raw JSON tool calls like '{{"name": "..."}}' in your chat response.
        4. If a user asks to delete or remove an expense, you MUST use the 'delete_expense' tool by finding the relevant ID or asking for clarification.
        
        ALLOWED CATEGORIES:
        <expense_categories>
        {expense_categories}
        </expense_categories>

        The active customer_id for all transactions is: {customer_id}
        
        Always provide brief, professional, and helpful responses."""
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