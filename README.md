# Loadpath for Claude

A Claude plugin with one skill, `loadpath-plans`: ask Claude for a workout or a program
and get a link that opens it in [Loadpath](https://getloadpath.com), the iPhone strength
training app. Nothing is saved until you tap Save in the app.

## Add it

- **Claude (claude.ai, desktop, mobile):** from the Claude directory, once listed.
  Until then: zip the `skills/loadpath-plans` folder and upload it under
  Customize → Skills (code execution must be on).
- **Claude Code:** `/plugin marketplace add AAimson/loadpath-claude`, then
  `/plugin install loadpath@loadpath`.
