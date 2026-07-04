"""Order response schema - enforces API contract between place_order() and callers.

This module defines the response format for all order operations.
Using TypedDict/Pydantic ensures callers can't accidentally check for wrong keys.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class OrderResponse(BaseModel):
    """Response from place_order() - SINGLE SOURCE OF TRUTH for order response format."""

    status: Literal["FILLED", "REJECTED", "ERROR", "PENDING"]
    order_id: str = Field(..., description="Unique order identifier")
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    side: Literal["BUY", "SELL"]
    quantity: float = Field(..., description="Order quantity")
    fill_price: float = Field(..., description="Actual fill price")
    fee: float = Field(default=0.0, description="Trading fee charged")
    timestamp: str = Field(..., description="Order timestamp (ISO format)")
    
    # Optional fields for specific scenarios
    realized_pnl: Optional[float] = Field(default=None, description="P&L if SELL order")
    error: Optional[str] = Field(default=None, description="Error message if status=ERROR")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "FILLED",
                "order_id": "uuid-123",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": 0.001,
                "fill_price": 45000.50,
                "fee": 0.01,
                "timestamp": "2026-07-04T10:30:49Z",
                "realized_pnl": None,
                "error": None,
            }
        }


def validate_order_response(result: dict) -> OrderResponse:
    """Validate and parse order response.
    
    Raises ValidationError if response doesn't match schema.
    This prevents silent failures from missing keys.
    
    Args:
        result: Response dict from place_order()
        
    Returns:
        OrderResponse with validated fields
        
    Raises:
        pydantic.ValidationError: If response doesn't match schema
    """
    return OrderResponse(**result)
