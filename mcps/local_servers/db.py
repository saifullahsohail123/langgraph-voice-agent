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