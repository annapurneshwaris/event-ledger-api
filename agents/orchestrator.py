#!/usr/bin/env python3
"""Runnable AI-SDLC orchestrator.

Demonstrates the three-agent workflow (design -> dev -> qa) as actual, executable
LLM passes against the Anthropic Messages API. Each agent loads its role prompt
from the matching ``.claude/agents/<name>.md`` definition (the same files Claude
Code uses), runs against the shared task, and emits an artifact under
``agents/output/``.

This is a thin, dependency-light harness — not a framework — so it is easy to read
and defend in a walkthrough. It mirrors how the real repo was produced with Claude
Code subagents; here the same definitions are driven programmatically end to end.

Usage
-----
    export ANTHROPIC_API_KEY=sk-...
    python agents/orchestrator.py            # run the full pipeline
    python agents/orchestrator.py --agent design-agent   # run a single agent
    python agents/orchestrator.py --dry-run  # print the plan without API calls

Requires: ``pip install anthropic`` (listed in requirements-dev.txt).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
OUTPUT_DIR = REPO_ROOT / "agents" / "output"

MODEL_DEFAULT = "claude-sonnet-4-5-20250929"

# The shared task all agents work against.
TASK = (
    "Build an Event Ledger API that ingests financial transaction events which may "
    "arrive out of order and more than once. It must support submitting an event, "
    "fetching one by id, listing an account's events in chronological order, and "
    "returning an account's net balance (sum of credits minus debits). It must be "
    "idempotent on eventId and tolerant of out-of-order arrival."
)

# Pipeline: agent name -> the artifact it is responsible for producing.
PIPELINE = [
    ("design-agent", "DESIGN.md", "Produce the design document and Mermaid diagrams."),
    ("dev-agent", "IMPLEMENTATION_NOTES.md",
     "Describe the implementation plan: layers, logging, audit trail, idempotency "
     "strategy, and the commit sequence you would make."),
    ("qa-agent", "TEST_PLAN.md",
     "Produce the test plan: the requirement-to-test mapping and the coverage "
     "strategy, one test area per requirement."),
]


def load_agent(name: str) -> tuple[str, str]:
    """Read a Claude Code agent definition, returning (description, system_prompt).

    The body after the YAML frontmatter is the agent's system prompt.
    """
    path = AGENTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not fm_match:
        raise ValueError(f"{path} is missing YAML frontmatter")
    frontmatter, body = fm_match.group(1), fm_match.group(2).strip()
    # description may be a folded block scalar ("description: >" then indented lines).
    desc_match = re.search(
        r"description:\s*(?:[>|]\s*\n((?:\s+.+\n?)+)|(.+))", frontmatter
    )
    if desc_match:
        block, inline = desc_match.group(1), desc_match.group(2)
        description = (
            " ".join(line.strip() for line in block.strip().splitlines())
            if block else inline.strip()
        )
    else:
        description = name
    return description, body


def run_agent(name: str, instruction: str, prior_artifacts: dict[str, str]) -> str:
    """Execute one agent as a single Messages API call and return its output text."""
    from anthropic import Anthropic  # imported lazily so --dry-run needs no key

    _, system_prompt = load_agent(name)
    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    context = "\n\n".join(
        f"## Upstream artifact: {fname}\n{content}"
        for fname, content in prior_artifacts.items()
    )
    user_content = (
        f"TASK:\n{TASK}\n\n"
        f"YOUR ASSIGNMENT:\n{instruction}\n\n"
        f"{('CONTEXT FROM PRIOR AGENTS:' + chr(10) + context) if context else ''}"
    )

    message = client.messages.create(
        model=os.environ.get("LEDGER_AGENT_MODEL", MODEL_DEFAULT),
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AI-SDLC agent pipeline.")
    parser.add_argument("--agent", help="Run only this agent (e.g. design-agent).")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the plan and resolved prompts without calling the API.",
    )
    args = parser.parse_args()

    steps = [s for s in PIPELINE if not args.agent or s[0] == args.agent]
    if not steps:
        print(f"Unknown agent: {args.agent}", file=sys.stderr)
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}

    for name, artifact, instruction in steps:
        description, system_prompt = load_agent(name)
        print(f"\n=== {name} -> agents/output/{artifact} ===")
        print(f"role: {description.splitlines()[0][:90]}")

        if args.dry_run:
            print(f"[dry-run] would run with system prompt ({len(system_prompt)} chars) "
                  f"and produce {artifact}")
            continue

        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY not set; re-run with --dry-run to preview.",
                  file=sys.stderr)
            return 1

        output = run_agent(name, instruction, artifacts)
        (OUTPUT_DIR / artifact).write_text(output, encoding="utf-8")
        artifacts[artifact] = output
        print(f"wrote {len(output)} chars")

    print("\nPipeline complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
