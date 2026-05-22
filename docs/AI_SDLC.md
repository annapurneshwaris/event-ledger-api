# AI-Assisted SDLC: How This Repo Was Built

This project was built with an AI-augmented workflow using **Claude Code**,
structured around three role-specialized agents that map directly to the SDLC
phases. This document explains the workflow, the agents, and which deliverable
each one owns — so the "AI engineering practices" can be evaluated alongside the
working solution.

## The three agents

Each agent is a real Claude Code subagent definition under
[`.claude/agents/`](.claude/agents/) — a Markdown file with YAML frontmatter
(`name`, `description`, `tools`, `model`) and a system-prompt body. They share a
common playbook via the [`ledger-conventions`](.claude/skills/ledger-conventions)
skill, which holds the invariants (immutable events, derived balance, `eventId`
primary key) so handoffs stay consistent.

| Agent | SDLC phase | Owns these deliverables |
|---|---|---|
| [`design-agent`](.claude/agents/design-agent.md) | Design | `docs/DESIGN.md` — architecture, ER, and sequence diagrams (Mermaid) |
| [`dev-agent`](.claude/agents/dev-agent.md) | Development | `app/` implementation, structured JSON logging, the `audit_log` table, error handling, and the incremental commit history |
| [`qa-agent`](.claude/agents/qa-agent.md) | QA | `tests/` suite and `docs/TEST_COVERAGE.md` (coverage report) |

This mirrors the three roles requested for the exercise: a design agent that
generates the design document and diagrams; a development agent that implements
error handling, logging, auditing, and meaningful commits; and a QA agent that
creates unit tests and coverage reports.

## Two ways the agents are demonstrated

**1. As Claude Code subagents (how the repo was actually built).**
During development, work was delegated to each subagent in turn within a Claude
Code session — for example, "Use the design-agent to draft the design doc," then
"Use the dev-agent to implement the persistence layer," then "Use the qa-agent to
cover idempotency." Each runs in its own context and returns its result, which is
why the commit history reads as a clean design → build → test progression.

**2. As a runnable orchestrator (proof it executes).**
[`agents/orchestrator.py`](agents/orchestrator.py) drives the same three agent
definitions programmatically against the Anthropic Messages API. It loads each
agent's system prompt from its `.claude/agents/*.md` file, runs the pipeline
design → dev → qa (feeding each agent the prior agent's output), and writes the
generated artifacts to `agents/output/`.

```bash
pip install -r requirements-dev.txt
export ANTHROPIC_API_KEY=sk-...

python agents/orchestrator.py            # full pipeline
python agents/orchestrator.py --agent design-agent   # one agent
python agents/orchestrator.py --dry-run  # preview without API calls
```

The `--dry-run` mode needs no API key and prints the resolved pipeline and
prompts, so the wiring can be inspected offline.

## Why this structure

- **Separation of concerns at the agent level** mirrors the separation in the code:
  design decides *what and why*, dev implements *how*, QA proves *that it works*.
- **Shared conventions skill** prevents the agents from drifting — all three read
  the same invariants, so the design doc, the code, and the tests agree on the
  data model and the idempotency contract.
- **Definitions + a runnable harness** means the agents are not just described;
  they are inspectable files and an executable pipeline.

## Honesty note

The committed `app/`, `tests/`, and `docs/` artifacts are the reviewed output of
the Claude Code subagent workflow described above, with human review at each
handoff. The `agents/orchestrator.py` harness reproduces the *workflow shape*
end-to-end and regenerates planning artifacts into `agents/output/`; those
generated files are not committed (the directory ships empty) so what you review
is the human-reviewed solution, not unverified machine output.
