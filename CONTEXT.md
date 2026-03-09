# CutAgent Context Discipline

Workspace media analysis can return very large JSON payloads. To preserve agent context window:

- Use field masks on high-volume analysis calls:
  - `cutagent probe <file> --fields path,duration,width,height`
  - `cutagent summarize <file> --fields summary.path,summary.suggested_cut_points`
- Use streaming output for list-heavy responses:
  - `cutagent scenes <file> --response-format ndjson`
  - `cutagent frames <file> --response-format ndjson`
  - `cutagent audio-levels <file> --response-format ndjson`
- Prefer schema introspection over static prompt stuffing:
  - `cutagent schema index`
  - `cutagent schema operation <name>`
  - `cutagent schema edl`
- Validate before mutation:
  - `cutagent op <name> --dry-run --json '{...}'`
  - `cutagent execute <edl> --dry-run`
