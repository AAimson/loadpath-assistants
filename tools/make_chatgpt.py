#!/usr/bin/env python3
"""Copy the Claude plugin's skill into the ChatGPT plugin.

    python3 tools/make_chatgpt.py

Writes chatgpt/skills/loadpath-plans/ from plugin/skills/loadpath-plans/, changing only
what differs for ChatGPT: the App Store link's campaign (ct=chatgpt), and no "free" in
the reply, since OpenAI's plugin guidelines rule out advertising pricing. Edit the skill
in plugin/ and run this (sync_from_app.py runs it too); never edit chatgpt/skills/ by hand.
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "plugin", "skills", "loadpath-plans")
TARGET = os.path.join(ROOT, "chatgpt", "skills", "loadpath-plans")

CHANGES = [
    ("ct=claude-skill", "ct=chatgpt"),
    ("it's free on the App Store,", "it's on the App Store,"),
]


def for_chatgpt(text):
    for old, new in CHANGES:
        if old not in text:
            raise ValueError(f"SKILL.md no longer has {old!r}: update CHANGES in tools/make_chatgpt.py")
        text = text.replace(old, new)
    return text


def main():
    shutil.rmtree(TARGET, ignore_errors=True)
    shutil.copytree(SOURCE, TARGET)
    path = os.path.join(TARGET, "SKILL.md")
    with open(path, encoding="utf-8") as f:
        text = for_chatgpt(f.read())
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {os.path.relpath(TARGET, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
