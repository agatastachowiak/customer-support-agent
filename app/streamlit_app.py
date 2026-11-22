"""Streamlit chat interface for the Lumen Market support agent."""
import asyncio
import sys
import threading
from pathlib import Path

import anthropic
import streamlit as st
from dotenv import load_dotenv
from mcp import Client

ROOT = Path(__file__).resolve().parents[1]                      # project folder
sys.path.insert(0, str(ROOT / "src" / "support_agent"))         # so I can import agent.py
import agent  # noqa: E402

load_dotenv(ROOT / ".env")                                      # loads the API key


# --- Background worker: keeps one MCP connection open between Streamlit reruns ---
async def _worker(queue):
    claude = anthropic.AsyncAnthropic()
    async with Client(agent.MCP_SERVER) as mcp_client:          # start the MCP server once
        listed = await mcp_client.list_tools()
        tools = [agent.to_claude_tool(t) for t in listed.tools] + [agent.ESCALATION_TOOL]
        while True:                                             # handle requests one by one
            messages, future = await queue.get()                # wait for the next order at the hatch 
            try:
                future.set_result(await agent.answer(mcp_client, claude, messages, tools))  #run the agent, ring the bell
            except Exception as e:
                future.set_exception(e)                         #pass errors back to the page too


async def _make_queue():
    return asyncio.Queue()                                      # the hatch


async def _submit(queue, messages):
    future = asyncio.get_running_loop().create_future()         # the bell: empty until the answer is ready
    await queue.put((messages, future))                         # put the conversation through the hatch
    return await future                                         # wait for the bell


@st.cache_resource                                              # run once per app, then reuse the result
def get_backend():
    """Created once per app: an event loop in a background thread, running the worker."""
    loop = asyncio.new_event_loop()                                     # a separate async line
    threading.Thread(target=loop.run_forever, daemon=True).start()      # runs in the background, so the page remains responsive
    queue = asyncio.run_coroutine_threadsafe(_make_queue(), loop).result()
    asyncio.run_coroutine_threadsafe(_worker(queue), loop)              # start the back room: MCP connection + waiting for requests
    return loop, queue

def ask_agent(messages):
    """Send the conversation to the back room and wait for the agent's answer."""
    loop, queue = get_backend()
    return asyncio.run_coroutine_threadsafe(_submit(queue, messages), loop).result(timeout=180) # give up after 3 minutes


# --- Page -----------------------------------------------------------------------
st.set_page_config(page_title="Lumen Market Support", page_icon="💬")   # browser tab title and icon
st.title("Lumen Market Support")
st.caption("Demo of an AI support agent for a fictional shop. "
           "Simulated date: 17 November 2026. All customers and orders are synthetic.")

with st.sidebar:                                                        # left panel: help for people trying the demo
    st.header("Try it")
    st.markdown(
        "Test customers (email · order):\n"
        "- emma.devries@example.com · ORD-1001 (return possible)\n"
        "- lucas.jansen@example.com · ORD-1002 (return window closed)\n"
        "- sophie.bakker@example.com · ORD-1003 (late parcel)\n"
        "- daan.visser@example.com · ORD-1004 (not shipped yet)\n"
        "- julia.smit@example.com · ORD-1005 (warranty)\n"
        "- mila.mulder@example.com · ORD-1007 (expensive laptop)\n"
    )
    st.caption(f"Model: {agent.MODEL}")
    if st.button("New conversation"):
        st.session_state.clear()                                        # forget the conversation
        st.rerun()                                                      # redraw the empty page

# st.session_state is Streamlit's memory: it survives the rerun after every message
if "api_messages" not in st.session_state:
    st.session_state.api_messages = []   # full history for Claude, incl. tool calls
    st.session_state.display = []        # what the user sees: (role, text, tools)

# Redraw the conversation so far (the page is rebuilt from scratch on every rerun)
for role, text, tools in st.session_state.display:
    with st.chat_message(role):
        st.markdown(text)
        if tools:
            st.caption("Tools used: " + ", ".join(tools))   # shows the agent’s decisions

# A new message: := stores the input in prompt and checks that it isn't empty
if prompt := st.chat_input("Ask a question about your order or our policies"):
    st.session_state.display.append(("user", prompt, []))
    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.api_messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant"):
        with st.spinner("Looking into it..."):              # loading animation while the agent works
            reply, tool_log = ask_agent(st.session_state.api_messages)
        tools = [call["tool"] for call in tool_log]
        st.markdown(reply)
        if tools:
            st.caption("Tools used: " + ", ".join(tools))
        if "escalate_to_human" in tools:
            st.info("This conversation was handed over to the human support team.") # make escalation visible
    st.session_state.display.append(("assistant", reply, tools))                    # remember it for the next rerun