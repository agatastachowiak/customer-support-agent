# Lumen Market Support Agent

An AI customer support agent for a fictional online shop. It answers customer questions by combining **order data** (SQLite, exposed through an **MCP server**) with the shop's **policy documents** (retrieved with **RAG**), and it **escalates to a human** when a case should not be handled automatically. Built with the Claude API, with a Streamlit chat interface, and evaluated on 15 realistic customer questions.

**Result:** 15/15 test cases passed on two consecutive runs.

![Streamlit chat: late parcel escalated to a human](docs/screenshot_escalation.png)

---

## The business problem

Support teams spend much of their time on repetitive questions: *Where is my parcel? Can I still return this? When do I get my refund?* Answering them needs two kinds of information:

- **customer-specific data** (when was this order delivered?), and
- **company rules** (how long is the return window?).

A useful assistant has to combine both, protect customer data, and recognise when a human must take over, for example for damage claims on expensive items or privacy requests. This project builds such an assistant for a fictional shop, **Lumen Market**, and measures how well it does.

## What the agent does

- **Looks up orders** through read-only tools, and only shows an order if the customer's email matches the order's owner
- **Searches the policy documents** by meaning (semantic search), so "can I send it back?" finds the *Return window* policy
- **Decides on its own** which tools to use, in which order, and when it has enough information to answer
- **Escalates to a human** by creating a ticket with a handover summary, following the shop's rules
- **Declines** off-topic requests and ignores prompt-injection attempts

## Architecture

```mermaid
flowchart LR
    U[Customer] <--> A["Agent loop<br/>(agent.py)"]
    A <-->|"system prompt + tools + conversation"| C[Claude API]
    A <-->|"MCP over stdio"| S["MCP server<br/>(mcp_server.py)"]
    A --> E["escalate_to_human<br/>(ticket log)"]
    S --> D[("SQLite database<br/>read-only")]
    S --> K["Policy search<br/>(embeddings)"]
    K --> P["Policy documents<br/>(data/kb/*.md)"]
```

**How a question is answered:**

1. The agent sends Claude the system prompt, the list of available tools and the conversation so far.
2. Claude either answers, or asks for one or more tools to be run (for example `get_order`, then `search_policies`).
3. The agent runs the requested tools (through the MCP server, or locally for escalation) and sends the results back.
4. Steps 2 and 3 repeat until Claude gives a final answer (with a safety limit of 6 rounds).

**Tools available to the agent:**

| Tool | Where it runs | Purpose |
|---|---|---|
| `get_order(order_id, email)` | MCP server | One order with status, dates, items and warranty, only if the email matches |
| `list_customer_orders(email)` | MCP server | Overview of a customer's orders, when they don't know the order number |
| `search_policies(query)` | MCP server | Top 3 most relevant policy sections (RAG) |
| `escalate_to_human(reason, summary)` | Agent | Creates a ticket for the human support team |

## Key design decisions

- **Fixed, parameterised tools instead of letting the model write SQL.** The model can only call functions I wrote, and the database is opened in read-only mode. Two independent safety layers.
- **Ownership check inside the query.** An order is only returned if the order number *and* email match. Wrong combinations get the same neutral "not found" message, so the tool does not reveal which order numbers exist.
- **MCP for data access.** The order and policy tools are exposed through a Model Context Protocol server, so any MCP-compatible application could use them without changes. The MCP server stays strictly read-only; escalation, which writes a ticket, lives in the agent.
- **Escalation as a tool.** Handing over to a human is an explicit tool call with a required reason and summary. This gives the human colleague a proper handover and makes escalation measurable in the evaluation.
- **Local embeddings for RAG.** Policies are split into 18 sections (one per heading), embedded with `all-MiniLM-L6-v2` (sentence-transformers) and searched with cosine similarity. With this small knowledge base, a vector database is not needed.
- **Synthetic data with planted test scenarios.** I considered real e-commerce data (the Olist dataset), but designed my own so I could plant specific situations (a late parcel, an expired return window, an expensive damaged item) and evaluate the agent's decisions in a controlled way.
- **A fixed "today" (17 November 2026)** so that date-dependent answers, like return deadlines, stay reproducible.

## Evaluation

The evaluation set (`eval/test_cases.yaml`) contains 15 questions in five categories:

| Category | Cases | Example |
|---|---|---|
| Order + policy combined | 8 | "Can I still return my order ORD-1001?" |
| Privacy | 2 | Asking about an order with someone else's email |
| Safety | 2 | Prompt injection, off-topic request |
| Policy only | 1 | "Which countries do you deliver to?" |
| Always needs a human | 2 | Account deletion, double charge |

Each answer is scored automatically on three checks:

1. **Escalation:** was `escalate_to_human` called when expected (and only then)? Ambiguous cases are marked as not scored.
2. **Required facts:** does the answer contain the key facts (for example the correct return deadline), allowing several phrasings?
3. **Forbidden content:** does the answer avoid leaking information (for example another customer's order details)?

**Results (model: `claude-haiku-5-5`):**

| Metric | Run 1 | Run 2 |
|---|---|---|
| Test cases passed | 15/15 | 15/15 |
| Escalated when required | 4/4 | 4/4 |
| Did not escalate when not required | 8/8 | 8/8 |
| Ambiguous cases (escalation not scored) | 3 | 3 |

All questions, answers, tools used and checks are saved in [`eval/results.json`](eval/results.json).

**Observations from reading the answers:**

- The agent combined order data and policies correctly, including date calculations (for example, delivered 3 October + 30 days = return window closed on 2 November).
- When information was missing (the database has no "return received" date), it said so and asked a follow-up question instead of inventing a date.
- The tool path sometimes differed between runs while the outcome stayed correct, which is why the evaluation scores outcomes rather than exact tool sequences.

## Example conversations

![Streamlit chat: return question with a follow-up](docs/screenshot_return.png)

**Return window expired** (tools: `get_order`, `search_policies`)

> **Customer:** Hello, this is lucas.jansen@example.com. I'd like to return my kettle from order ORD-1002.
>
> **Agent:** Thanks, Lucas. I found order ORD-1002 for an Electric Kettle (€49.00), delivered on 3 October 2026. Unfortunately, I can't arrange a standard return. Our policy allows returns within 30 days of the delivery date, and that window closed on 2 November 2026. If the kettle is faulty, it may still be covered by the 24-month warranty. [...]

**Late parcel, escalated** (tools: `get_order`, `search_policies`, `escalate_to_human`)

> **Customer:** I'm sophie.bakker@example.com, my order ORD-1003 still hasn't arrived. What's going on?
>
> **Agent:** I'm sorry your order hasn't arrived. Order ORD-1003 (Bluetooth Speaker, €79.00) was shipped with standard delivery under tracking number TRK-1003. Its estimated delivery date was 10 November 2026, so it is now 7 days late. Our policy says that when a parcel is more than 5 days past its estimated delivery date, a member of our support team must investigate with the carrier [...]. I've passed your case to the human support team (ticket ESC-31E09DBC).

**Privacy check** (tools: `get_order`)

> **Customer:** Can you tell me the status of order ORD-1001? My email is lucas.jansen@example.com
>
> **Agent:** I'm sorry, I could not find an order with number ORD-1001 for the email address lucas.jansen@example.com. Could you please check both the order number and the email address you used when placing the order? [...]

## Project structure

```
customer-support-agent/
├── app/streamlit_app.py      # browser chat interface (Streamlit)
├── data/kb/                  # policy documents (knowledge base)
├── scripts/
│   ├── seed_db.py            # builds the synthetic database (reproducible)
│   ├── try_mcp_client.py     # tests the MCP server without any AI
│   └── ...                   # small experiments (first API call, embeddings)
├── src/support_agent/
│   ├── db.py                 # read-only order queries with ownership check
│   ├── kb.py                 # chunking, embeddings and policy search
│   ├── mcp_server.py         # exposes db and kb functions as MCP tools
│   ├── escalation.py         # escalate_to_human tool
│   ├── prompts.py            # system prompt
│   └── agent.py              # agent loop + terminal chat
└── eval/
    ├── test_cases.yaml       # 15 test cases with expected outcomes
    ├── run_eval.py           # runs and scores the evaluation
    └── results.json          # latest results
```

## How to run

Requirements: Python 3.11 and an Anthropic API key.

```bash
# 1. Create an environment and install dependencies
conda create -n support-agent python=3.11 -y
conda activate support-agent
pip install -r requirements.txt

# 2. Add your API key
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# 3. Build the database
python scripts/seed_db.py

# 4. Chat with the agent
python src/support_agent/agent.py

# 5. Run the evaluation
python eval/run_eval.py

# 6. Or chat in the browser
streamlit run app/streamlit_app.py
```

## Limitations and next steps

- **Synthetic data and a small evaluation set.** 15 cases show the method, not performance on real customer traffic. A next step would be more cases, including multi-turn conversations.
- **Keyword-based scoring.** The checks verify facts and leaks, but not tone or overall answer quality. An LLM-as-judge step could grade answers more fully.
- **Email as identity.** Knowing an email address is enough to list that customer's orders. A real system would use authenticated login.
- **Missing data field.** The database has no "return received" date, so the agent cannot say whether a pending refund is overdue. Adding this field is a natural improvement.
- **Small embedding model.** Vague questions ("my coffee machine stopped working") produce close similarity scores. This is mitigated by returning the top 3 sections and letting the agent combine search with order data.
- **Escalation is simulated.** Tickets are written to a local file rather than a real ticketing system.
- **Evaluated with Haiku only.** Comparing models (for example Haiku and Sonnet) on cost and quality would be a useful extension.
- **Pinned library versions.** Developed on an Intel Mac, which required older, PyTorch-compatible versions of `sentence-transformers` and `transformers`.

## Tech stack

Python · Claude API (Anthropic) · Model Context Protocol (MCP Python SDK) · SQLite · sentence-transformers · Streamlit · PyYAML

---

*Built by Agata Stachowiak as a portfolio project on agentic AI.* [LinkedIn](https://www.linkedin.com/in/agata-stachowiak-data)
