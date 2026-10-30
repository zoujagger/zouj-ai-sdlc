---
type: tool_order
before: { tool: Bash, input_match: "unittest|make (test|check)" }
after: { tool: Write, input_match: "src/(?!__init__)" }
---
