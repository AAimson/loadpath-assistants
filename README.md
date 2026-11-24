# Loadpath for Claude

A Claude plugin with one skill, `loadpath-plans`: ask Claude for a workout or a program
and get a link that opens it in [Loadpath](https://getloadpath.com), the iPhone strength
training app. Nothing is saved until you tap Save in the app. Plans open in Loadpath 2.7
or later.

## Add it

- **Claude (claude.ai, desktop, mobile):** from the Claude directory, once listed.
  Until then: zip the `plugin/skills/loadpath-plans` folder and upload it under
  Customize → Skills (code execution must be on).
- **Claude Code:** `/plugin marketplace add AAimson/loadpath-claude`, then
  `/plugin install loadpath@loadpath`.

## What's here

- `plugin/`: the plugin, as the directory lists it (submit it with plugin path `plugin`).
  It holds only Markdown, JSON and images: the directory takes scripts only from Verified
  organizations.
- `tools/build_link.py`: checks a plan as the app does (its `PlanDocument.validated()` and
  JSON decoding) and prints its link. `python3 tools/build_link.py plan.json`
- `tools/sync_from_app.py`: copies what the app defines into the plugin and `tools/`.
- `tests/`: `build_link.py` against the app's own test fixtures, and the skill's examples
  and link code against `build_link.py`.

## Keep it in step with the app

`plugin/skills/loadpath-plans/reference/format.md`, `reference/lifts.md` and
`tools/lifts.json` are copies of what the app defines. After a change to the app's
`ExerciseCatalog.json` or `docs/plan-format.md`:

```bash
python3 tools/sync_from_app.py ../fitness-app
python3 -m unittest discover tests
```

The tests mirror the fixtures in the app's `PlanDocumentTests.swift`; when those change,
change `tests/test_build_link.py` to match.
