"""Run the evaluation set against the support agent and score the results."""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import yaml
from dotenv import load_dotenv
from mcp import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "support_agent"))   # to import agent.py
import agent  # noqa: E402

CASES_FILE = ROOT / "eval" / "test_cases.yaml"
RESULTS_FILE = ROOT / "eval" / "results.json"


def check_case(case, reply, tool_log):
    """Score one answer. Each check is True (pass), False (fail) or None (not scored)."""
    text = reply.lower()
    escalated = any(call["tool"] == "escalate_to_human" for call in tool_log)
    expected = case.get("expect_escalation")

    checks = {
        "escalation": None if expected is None else escalated == expected, # if expected is None, the case is ambiguous and either answer is acceptable
        "must_include": all(    # All groups must match, and within a group any one variant is enough
            any(variant.lower() in text for variant in group)
            for group in case.get("must_include", [])
        ),
        "must_not_include": not any(    # passes only if none of the forbidden strings appear, Everything is compared in lowercase
            forbidden.lower() in text for forbidden in case.get("must_not_include", [])
        ),
    }
    passed = all(result is not False for result in checks.values()) # passed is true if no check is False; None doesn’t count as failing
    return escalated, checks, passed


async def main():
    load_dotenv()
    cases = yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))
    claude = anthropic.AsyncAnthropic()
    results = []

    async with Client(agent.MCP_SERVER) as mcp_client:
        listed = await mcp_client.list_tools()
        tools = [agent.to_claude_tool(t) for t in listed.tools] + [agent.ESCALATION_TOOL]

        for case in cases:
            messages = [{"role": "user", "content": case["question"]}]   # fresh conversation per case, Each test is independent, so an earlier answer can’t influence a later one.
            reply, tool_log = await agent.answer(mcp_client, claude, messages, tools)
            escalated, checks, passed = check_case(case, reply, tool_log)

            results.append({
                "id": case["id"],
                "question": case["question"],
                "reply": reply,
                "tools_used": [call["tool"] for call in tool_log],
                "escalated": escalated,
                "checks": checks,
                "passed": passed,
            })
            status = "PASS" if passed else "FAIL"
            print(f"{status}  {case['id']:<26} tools: {[c['tool'] for c in tool_log]}") #I can immediately see why a case failed
            if not passed:
                print(f"      checks: {checks}")
                print(f"      reply:  {reply[:300]}")

    # --- Summary ---------------------------------------------------------------
    n_passed = sum(r["passed"] for r in results)
    scored = [r for r in results if r["checks"]["escalation"] is not None]
    esc_correct = sum(r["checks"]["escalation"] for r in scored)
    print(f"\nOverall: {n_passed}/{len(results)} test cases passed")
    print(f"Escalation decisions correct: {esc_correct}/{len(scored)} (cases where it was scored)")

    RESULTS_FILE.write_text(json.dumps({
        "model": agent.MODEL,
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "passed": n_passed,
        "total": len(results),
        "results": results,
    }, indent=2, ensure_ascii=False))
    print(f"Full results saved to {RESULTS_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())