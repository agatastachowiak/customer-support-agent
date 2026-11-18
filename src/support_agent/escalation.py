"""Escalation: hand the conversation over to the human support team."""
import json
import uuid
from datetime import datetime
from pathlib import Path

TICKETS_FILE = Path(__file__).resolve().parents[2] / "data" / "escalations.jsonl"

# Tool definition in the Claude API format (written by hand, because this tool is not on the MCP server)
ESCALATION_TOOL = {
    "name": "escalate_to_human",
    "description": (
        "Hand the conversation over to the human support team by creating a ticket. "
        "Use this when the policies say a case is always handled by a human, when the "
        "customer is very upset or asks for a human, or when you cannot answer with "
        "your other tools. After calling it, tell the customer their case was passed on."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Short reason, e.g. 'parcel more than 5 days late' or "
                               "'damage claim for item over 500 euros'.",
            }, # describtion guides Claude to give a reason for the escalation, not just say "I escalated"
            "summary": {
                "type": "string",
                "description": "Summary for the human colleague: customer email, order "
                               "number, what the customer wants, and what you already found.",
            },
        },
        "required": ["reason", "summary"], #Claude must always say why it escalates and summarise the case. The reason will also show why the agent escalated, not only that it did.
    },
}


def escalate_to_human(reason: str, summary: str) -> dict:
    """Create a support ticket for the human team (saved as one line in a JSONL file)."""
    ticket = {
        "ticket_id": f"ESC-{uuid.uuid4().hex[:8].upper()}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "reason": reason,
        "summary": summary,
    }
    TICKETS_FILE.parent.mkdir(exist_ok=True)
    with TICKETS_FILE.open("a", encoding="utf-8") as f: #generates a random unique ID, shortened to 8 characters
        f.write(json.dumps(ticket) + "\n")
    return {"status": "escalated", "ticket_id": ticket["ticket_id"]}


if __name__ == "__main__":
    print(escalate_to_human(
        reason="test",
        summary="Test ticket created by running escalation.py directly.",
    ))