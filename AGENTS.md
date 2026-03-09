# CutAgent Agent Guidance

This repository is designed for AI-agent command execution. Follow these invariants:

1. Always discover capabilities first:
   - `cutagent capabilities`
   - `cutagent schema index`
2. For single edits, prefer payload-first execution:
   - `cutagent schema operation <name>`
   - `cutagent op <name> --dry-run --json '{...}'`
   - `cutagent op <name> --json '{...}'`
3. For multi-step edits, use EDL:
   - `cutagent validate ...`
   - `cutagent execute ...`
4. For large responses, reduce context usage:
   - `--fields` for projections
   - `--response-format ndjson` for list-heavy analysis
5. For safety-sensitive contexts:
   - Use `--dry-run` before mutating operations
   - Use `--sanitize-output basic` when relaying content to downstream LLM reasoning
6. Never rely on human-formatted stdout. CutAgent stdout is JSON/NDJSON only.
