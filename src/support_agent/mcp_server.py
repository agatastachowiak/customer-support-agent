"""MCP server: exposes Lumen Market's read-only database tools to any MCP client."""
from mcp.server.mcpserver import MCPServer

import db  # my own db.py, in the same folder

mcp = MCPServer("lumen-market-support") # class from the library


@mcp.tool() # a decorator: a label placed above a function that changes how it’s used. It says “register this function as a tool”.
def get_order(order_id: str, email: str) -> dict:
    """Look up one order by its order number (e.g. ORD-1001), including status,  
    dates, tracking number, refund date and the products in it (with warranty
    period). The customer's email address is required: the order is only
    returned if it belongs to that email."""
    return db.get_order(order_id, email) #docstring above: Claude does not see your code, only these descriptions. They are how it decides when to use a tool.


@mcp.tool()
def list_customer_orders(email: str) -> dict:
    """List all orders of the customer with this email address (order number,
    date, status, total), newest first. Use this when the customer does not
    know their order number."""
    return db.list_customer_orders(email)


if __name__ == "__main__":
    mcp.run(transport="stdio")