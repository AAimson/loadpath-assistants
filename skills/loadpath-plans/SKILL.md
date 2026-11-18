---
name: loadpath-plans
description: Build a strength training workout or program and hand back a link that opens it in Loadpath, the iPhone strength training app. Use when someone asks for a gym workout, training plan, routine or program (5/3/1, GZCLP, PPL, upper/lower, full body, a beginner plan, a variant of a named program) and mentions Loadpath, or wants it in an app, as a link, or ready to log.
---

# Loadpath plans

Loadpath opens a plan from a link as a preview; nothing is saved until the lifter taps
Save. Your job: write the plan in Loadpath's format, run the script that checks it and
builds the link, and give the lifter the link.

## 1. Settle what you need

You need: days per week, equipment (full gym, home dumbbells, bodyweight…), kg or lb, and
the goal (strength, size, general). Take what the lifter already said. Ask one short
question only for what is missing and matters; otherwise assume a full gym, kg, 3 days,
general strength, and say what you assumed.

## 2. Write the plan

Read `reference/format.md` for the format and `reference/lifts.md` for the lifts.

- Use lift names **exactly** as in `reference/lifts.md`, with their `id`. Pick a listed
  lift whenever one fits; an unlisted name makes the lifter match it by hand.
- Match a lift's kind: sets × reps, seconds (`sets` + `seconds`) or minutes/km.
- **Leave `weight` out.** Loadpath starts each lift from the lifter's own history.
- Give `unit` whenever a lift has a `step`.
- Use the progression rules Loadpath has (`linear`, `double` with `repsTo`, `percent`
  for training-max programs, `stages` for GZCLP tiers) instead of describing
  progression in words. For 5/3/1, use `percent` with `wave`s and weeks carrying `wave`.
- A program repeats its `weeks`; one week is enough for a plan that doesn't change week
  to week. Use `null` for rest days.
- Write only fields `reference/format.md` describes.

## 3. Build the link

Save the JSON to a file and run:

```bash
python3 scripts/build_link.py plan.json
```

- **ERROR** lines: Loadpath would refuse the plan. Fix them and run it again.
- **WARNING** lines: a lift name Loadpath won't match by itself. Switch to the suggested
  Loadpath lift when it is the same exercise, and run it again. Keep the name only when
  no listed lift is the same exercise; the lifter will match it in the app.
- Exit code 2 prints the plan as JSON instead of a link, because the link would be too long.

## 4. Reply

1. The plan in plain words: each workout's lifts with sets × reps, and how it progresses.
   Keep it short.
2. The link, on its own line: **Open in Loadpath**. It opens the app on an iPhone with
   Loadpath; elsewhere it opens a page that shows the plan and how to get the app.
3. If they don't have Loadpath: it's free on the App Store,
   https://apps.apple.com/app/apple-store/id6764851498?pt=1053933&ct=claude-skill&mt=8

**If you can't run code**, or the script gave JSON: give the plan's JSON in a code block
and tell the lifter to copy it, then in Loadpath tap Train → + → Import from Text.
Never write a link by hand; it holds compressed data you can't produce reliably without
the script.
