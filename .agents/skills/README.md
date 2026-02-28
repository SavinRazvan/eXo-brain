# Skills Directory (`.agents/skills`)

This directory is the project-level, standards-friendly location for Agent Skills.

## Why This Exists

- Cursor already loads project skills from `.cursor/skills/`.
- The open skills ecosystem also uses `.agents/skills/`.
- Keeping this directory makes the repository portable across agents/tools that follow the same convention.

## Recommended Structure

Each skill should be a folder with `SKILL.md`:

```text
.agents/
└── skills/
    └── my-skill/
        └── SKILL.md
```

Optional per-skill folders:

- `scripts/` for executable helpers
- `references/` for longer docs
- `assets/` for templates/static resources

## Current Project State

- Active skills currently live in `.cursor/skills/`.
- You can mirror/migrate them here over time for cross-tool compatibility.
