# TRP1 Week 2 – The Automaton Auditor

Automated governance swarm using LangGraph for forensic code auditing.

## Structure

\`\`\`text
automaton-auditor/
├── src/
│   ├── __init__.py
│   ├── state.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── repo_tools.py
│   │   └── doc_tools.py
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── setup.py
│   │   ├── detectives.py
│   │   ├── judges.py
│   │   └── justice.py
│   └── graph.py
├── rubric/
│   └── week2_rubric.json
├── audit/
│   ├── report_onself_generated/
│   ├── report_onpeer_generated/
│   └── report_bypeer_received/
├── reports/
│   ├── interim_report.pdf
│   └── final_report.pdf
├── .env.example
├── Dockerfile
└── README.md
\`\`\`

## Setup

\`\`\`bash
uv sync
cp .env.example .env          # then fill in your keys
\`\`\`

## Next steps

- Paste the full rubric JSON into `rubric/week2_rubric.json`
- Implement state models → tools → nodes → graph
- Run self-audit and peer audits
