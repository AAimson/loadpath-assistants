#!/usr/bin/env python3
"""Rebuild the skill's copies of what the app defines, from a fitness-app checkout.

    python3 tools/sync_from_app.py ../fitness-app

Writes, under skills/loadpath-plans/:
  scripts/lifts.json    the catalogue's names, aliases, kinds and equipment
  reference/lifts.md    the same, as tables by category
  reference/format.md   docs/plan-format.md, without "What Share as Link sends"
                        (how the app shares a plan, which a plan's writer doesn't need)

Run it whenever the app's ExerciseCatalog.json or docs/plan-format.md changes, and
commit what changes.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "loadpath-plans")

KIND = {"Strength": "sets × reps", "Reps": "sets × reps, no weight", "Time": "seconds", "Cardio": "minutes / km"}

INTRO = """# Loadpath's lifts

Generated from the app's catalogue; don't edit by hand. Write `lift` exactly as in
**Name**, with its `id`. A lift's kind decides its fields: sets × reps (`sets`, `reps`
or `setList`), seconds (`sets` + `seconds`) or minutes / km (`minutes`, `km`).

"""

EXPORT_SECTION = "## What Share as Link sends"


def lifts(catalogue):
    entries = sorted(catalogue, key=lambda e: (e["category"], e["name"]))
    as_json = [{"id": e["id"], "name": e["name"], "aliases": e.get("aliases", []),
                "kind": e["loggingModeRaw"], "equipment": e["equipment"]} for e in entries]
    md = [INTRO]
    category = None
    for e in entries:
        if e["category"] != category:
            category = e["category"]
            md.append(f"\n## {category}\n\n| Name | id | Kind | Equipment | Also called |\n|---|---|---|---|---|\n")
        md.append(f"| {e['name']} | `{e['id']}` | {KIND[e['loggingModeRaw']]} | {e['equipment']} | "
                  f"{', '.join(e.get('aliases', []))} |\n")
    return json.dumps(as_json, indent=1, ensure_ascii=False) + "\n", "".join(md)


def format_doc(text):
    start = text.find(EXPORT_SECTION)
    if start < 0:
        return text
    end = text.find("\n## ", start + len(EXPORT_SECTION))
    return text[:start].rstrip("\n") + "\n" + (text[end:] if end >= 0 else "")


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    app = sys.argv[1]
    with open(os.path.join(app, "FitnessApp", "ExerciseCatalog.json"), encoding="utf-8") as f:
        lifts_json, lifts_md = lifts(json.load(f))
    with open(os.path.join(app, "docs", "plan-format.md"), encoding="utf-8") as f:
        format_md = format_doc(f.read())
    for path, text in [("scripts/lifts.json", lifts_json), ("reference/lifts.md", lifts_md),
                       ("reference/format.md", format_md)]:
        with open(os.path.join(SKILL, path), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
