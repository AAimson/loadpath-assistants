# Loadpath for AI assistants

A plugin with one skill, `loadpath-plans`, for Claude and for ChatGPT: ask for a workout or
a program and get a link that opens it in [Loadpath](https://getloadpath.com), the iPhone
strength training app. Nothing is saved until you tap Save in the app. Plans open in
Loadpath 2.7 or later.

## Add it

- **Claude (claude.ai, desktop, mobile):** from the Claude directory, once listed.
  Until then: zip the `plugin/skills/loadpath-plans` folder and upload it under
  Customize → Skills (code execution must be on).
- **Claude Code:** `/plugin marketplace add AAimson/loadpath-assistants`, then
  `/plugin install loadpath@loadpath`.
- **ChatGPT:** from the plugin directory (chatgpt.com/plugins), once listed.

## What's here

- `plugin/`: the Claude plugin, as the directory lists it (submit it with plugin path `plugin`).
  It holds only Markdown, JSON and images: the directory takes scripts only from Verified
  organizations.
- `chatgpt/`: the ChatGPT plugin (skills only), as OpenAI's plugin portal takes it. Its skill is
  the Claude one with the App Store link's campaign changed, written by `tools/make_chatgpt.py`;
  edit the skill in `plugin/` only. To submit, zip the folder's contents with `plugin.json` at
  the top of the zip, and upload it on the OpenAI Platform's Plugins page:

  ```bash
  (cd chatgpt && zip -r ../loadpath-chatgpt.zip . -x README.md)
  ```

- `tools/build_link.py`: checks a plan as the app does (its `PlanDocument.validated()` and
  JSON decoding) and prints its link. `python3 tools/build_link.py plan.json`
- `tools/sync_from_app.py`: copies what the app defines into both plugins and `tools/`.
- `tests/`: `build_link.py` against the app's own test fixtures, the skill's examples
  and link code against `build_link.py`, and the ChatGPT copy against the Claude skill.

## Keep it in step with the app

`reference/format.md` and `reference/lifts.md` in each plugin's skill, and `tools/lifts.json`,
are copies of what the app defines. After a change to the app's `ExerciseCatalog.json` or
`docs/plan-format.md`:

```bash
python3 tools/sync_from_app.py ../fitness-app
python3 -m unittest discover tests
```

After editing the skill itself, run `python3 tools/make_chatgpt.py`.

The tests mirror the fixtures in the app's `PlanDocumentTests.swift`; when those change,
change `tests/test_build_link.py` to match.
