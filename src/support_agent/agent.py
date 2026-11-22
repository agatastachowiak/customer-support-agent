"""Lumen Market support agent: Claude (the brain) + tools (the hands), in a loop."""
import asyncio
import json
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from mcp import Client, StdioServerParameters

from escalation import ESCALATION_TOOL, escalate_to_human  
from prompts import SYSTEM_PROMPT

MODEL = "claude-haiku-5-5"          # cheap and fast for development
MAX_ROUNDS = 6                      # safety limit: max tool rounds per customer message

# How to start the MCP server: "run mcp_server.py (next to this file) with this code"
MCP_SERVER = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).with_name("mcp_server.py"))],
)


# --- A: TRANSLATE MCP tool descriptions into the Claude API format ---------------
def to_claude_tool(mcp_tool):
    return {
        "name": mcp_tool.name,
        "description": mcp_tool.description,
        "input_schema": mcp_tool.input_schema,
    }

# --- B: THE AGENT (HANDS) ---------------
async def run_tool(mcp_client, name, tool_input):
    """Run a tool that Claude asked for and return its result as text."""
    try:
        if name == "escalate_to_human":                       # local tool
            return json.dumps(escalate_to_human(**tool_input))
        result = await mcp_client.call_tool(name, tool_input)  # MCP tool
        return result.content[0].text
    except Exception as e:                                     # never crash the conversation
        return json.dumps({"error": f"Tool failed: {e}"})

'''
One function decides where a tool lives (escalation local, rest in MCP).
tool_input unpacks Claude inputs {"reason": ..., "summary": ...} into named arguments. 
The try/except catches any tool failure and returns it as an error message instead of crashing. 
Claude can read “Tool failed” and tell the customer something sensible.
'''

# --- C: AGENT LOOP for one customer message (hand-brain loop)-------------------------------
async def answer(mcp_client, claude, messages, tools):
    """Let Claude use tools until it gives a final answer.
    Returns the answer text and a log of the tools that were called."""
    tool_log = []
    for _ in range(MAX_ROUNDS):                         #repeat, but at most 6 times (the safety limit)
        response = await claude.messages.create(        #ask Claude: system prompt + tools + full conversation
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})     # add Claude’s reply to the conversation (the memory)

        if response.stop_reason != "tool_use":                                  # final answer, so collect the text and return it
            text = "".join(b.text for b in response.content if b.type == "text")
            return text, tool_log

        tool_results = []                                                       # Claude asked for tools
        for block in response.content:                                          # run each requested tool and collect the results as one message 
            if block.type == "tool_use":
                result = await run_tool(mcp_client, block.name, block.input)
                tool_log.append({"tool": block.name, "input": block.input})     # records which tools were called
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,                                    # labels each result to which request it answers
                    "content": result,
                })
        messages.append({"role": "user", "content": tool_results})

        
    return ("Sorry, I couldn't complete this request. Please contact our support team.",
            tool_log)


# --- D: a simple chat in the terminal -------------------------------------------
"""It starts the MCP server once, gets the tools, and then loops: read your message → answer(...) → print the tools used and the reply. """ 

async def main():
    load_dotenv()
    claude = anthropic.AsyncAnthropic()

    async with Client(MCP_SERVER) as mcp_client:               # starts the MCP server
        listed = await mcp_client.list_tools()
        tools = [to_claude_tool(t) for t in listed.tools] + [ESCALATION_TOOL]
        print("Tools:", [t["name"] for t in tools])
        print("Lumen Market support - type 'quit' to stop.\n")

        messages = []                                          # the conversation = the memory
        while True:
            user_text = input("You: ").strip()
            if user_text.lower() in ("quit", "exit"):
                break
            if not user_text:
                continue
            messages.append({"role": "user", "content": user_text})
            reply, tool_log = await answer(mcp_client, claude, messages, tools)
            for call in tool_log:
                print(f"   [tool] {call['tool']} {json.dumps(call['input'])}")
            print(f"\nAgent: {reply}\n")


if __name__ == "__main__":
    asyncio.run(main())