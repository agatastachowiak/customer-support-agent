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
            }, # guides Claude to give a real reason, not just "I escalated"
            "summary": {
                "type": "string",
                "description": "Summary for the human colleague: customer email, order "
                               "number, what the customer wants, and what you already found.",
            },
        },
        "required": ["reason", "summary"], # reason + summary required: proper handover, and measurable in the eval 
    },
}


def escalate_to_human(reason: str, summary: str) -> dict:
    """Create a support ticket for the human team (saved as one line in a JSONL file)."""
    ticket = {
        "ticket_id": f"ESC-{uuid.uuid4().hex[:8].upper()}",             # random unique ID, e.g. ESC-3F9A1C2B
        "created_at": datetime.now().isoformat(timespec="seconds"),     # timestamp, e.g. 2026-11-19T14:15:02
        "reason": reason,                                               # why Claude escalated
        "summary": summary,                                             # handover for the human colleague
    }
    TICKETS_FILE.parent.mkdir(exist_ok=True)                            # make sure the data/ folder exists
    with TICKETS_FILE.open("a", encoding="utf-8") as f:                 # append: one JSON line per ticket
        f.write(json.dumps(ticket) + "\n")                              # dict -> JSON text, newline ends the line
    return {"status": "escalated", "ticket_id": ticket["ticket_id"]}    # Claude can share the ticket ID with the customer


if __name__ == "__main__":
    print(escalate_to_human(
        reason="test",
        summary="Test ticket created by running escalation.py directly.",
    ))