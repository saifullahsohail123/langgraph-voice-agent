from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import List, Optional
from sqlalchemy import ForeignKey, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session
from uuid import UUID, uuid4
from datetime import datetime
import os
from pydantic import BaseModel
from enum import Enum
import pandas as pd

load_dotenv()

# ----------------------------
# SQLAlchemy Models
# ----------------------------

class Base(DeclarativeBase):
     pass

class DBCustomer(Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(primary_key=True, index=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"), onupdate=datetime.now)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)

    expenses: Mapped[List["DBExpense"]] = relationship(back_populates="customer", cascade="all, delete-orphan")

class DBExpense(Base):
    __tablename__ = "expenses"

    id: Mapped[UUID] = mapped_column(primary_key=True, index=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"), onupdate=datetime.now)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False, server_default=text("other"))
    amount: Mapped[float] = mapped_column(nullable=False)

    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    customer: Mapped["DBCustomer"] = relationship(back_populates="expenses", foreign_keys=[customer_id])

# ----------------------------
# Pydantic Models
# ----------------------------

class Customer(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    first_name: str
    last_name: str
    email: str

class ExpenseCategory(str, Enum):
    MEALS = "meals"
    TRAVEL = "travel"
    LODGING = "lodging"
    ENTERTAINMENT = "entertainment"
    TRAINING = "training"
    GIFTS = "gifts"
    EDUCATION = "education"
    OFFICE_SUPPLIES = "office_supplies"
    OTHER = "other"

class Expense(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    name: str
    description: Optional[str]
    category: ExpenseCategory
    amount: float
    customer_id: UUID

# ----------------------------
# DB Session
# ----------------------------

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(url=os.getenv("SUPABASE_URI"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ----------------------------
# MCP Server
# ----------------------------

mcp = FastMCP("db")

@mcp.tool()
async def create_expense(
    customer_id: UUID,
    name: str,
    amount: float,
    category: ExpenseCategory,
    description: Optional[str] = None,
    ) -> str:
    """Create a new expense for the customer_id."""
    with SessionLocal() as session:
        new_expense = DBExpense(
            name=name,
            amount=amount,
            category=category.value,
            description=description,
            customer_id=customer_id,
            )
        session.add(new_expense)
        session.commit()
        session.refresh(new_expense)
    
    return Expense.model_validate(new_expense.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def list_expenses(customer_id: UUID) -> str:
    """List the customer's expenses. Returns a JSON list of expense objects."""
    with SessionLocal() as session:
        expenses = session.query(DBExpense).filter(DBExpense.customer_id == customer_id).all()
        # Convert to Pydantic models for clean serialization
        results = [Expense.model_validate(e.__dict__).model_dump() for e in expenses]
        import json
        return json.dumps(results, indent=2, default=str)

@mcp.tool()
async def update_expense(
    expense_id: UUID,
    name: Optional[str] = None,
    amount: Optional[float] = None,
    category: Optional[ExpenseCategory] = None,
    description: Optional[str] = None,
) -> str:
    """Update an existing expense."""
    with SessionLocal() as session:
        expense = session.query(DBExpense).filter(DBExpense.id == expense_id).first()
        if not expense:
            return f"❌ Expense with ID {expense_id} not found."
            
        if name is not None: expense.name = name
        if amount is not None: expense.amount = amount
        if category is not None: expense.category = category.value
        if description is not None: expense.description = description
        
        session.commit()
    return f"✅ Expense updated successfully."

@mcp.tool()
async def delete_expense(expense_id: UUID) -> str:
    """Delete an expense by its ID."""
    with SessionLocal() as session:
        expense = session.query(DBExpense).filter(DBExpense.id == expense_id).first()
        if not expense:
            return f"❌ Expense with ID {expense_id} not found."
        
        session.delete(expense)
        session.commit()
    return f"✅ Expense deleted successfully."

@mcp.tool()
async def delete_all_expenses(customer_id: UUID) -> str:
    """Delete ALL expenses for a customer. Use with caution!"""
    with SessionLocal() as session:
        session.query(DBExpense).filter(DBExpense.customer_id == customer_id).delete()
        session.commit()
    return "✅ All expenses deleted successfully."

if __name__ == "__main__":
    mcp.run(transport="stdio")