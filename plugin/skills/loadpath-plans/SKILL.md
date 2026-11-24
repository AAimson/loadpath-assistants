---
name: loadpath-plans
description: Build a strength training workout or program and hand back a link that opens it in Loadpath, the iPhone strength training app. Use when someone asks for a gym workout, training plan, routine or program (5/3/1, GZCLP, PPL, upper/lower, full body, a beginner plan, a variant of a named program) and mentions Loadpath, or wants it in an app, as a link, or ready to log.
---

# Loadpath plans

Loadpath opens a plan from a link as a preview; nothing is saved until the lifter taps
Save. Your job: write the plan in Loadpath's format, check it, build the link with code,
and give the lifter the link.

## 1. Settle what you need

You need: days per week, equipment (full gym, home dumbbells, bodyweight…), kg or lb, and
the goal (strength, size, general). Take what the lifter already said. Ask one short
question only for what is missing and matters; otherwise assume a full gym, kg, 3 days,
general strength, and say what you assumed.

## 2. Write the plan

Read `reference/format.md` for the format and `reference/lifts.md` for the lifts.

- Use lift names **exactly** as in `reference/lifts.md`, with their `id`. Pick a listed
  lift whenever one fits; an unlisted name makes the lifter match it by hand.
- Match a lift's kind: sets × reps, seconds (`sets` + `seconds`) or minutes/km. A lift
  is logged the way its Kind says, so write a hold (Plank, Side Plank, Dead Hang, Wall
  Sit…) as `sets` + `seconds`.
- **Leave `weight` out.** Loadpath fills weights from the lifter's own history; a
  training-max lift with no history asks for a 5-rep weight after saving.
- Always set the plan's top-level `unit` (`"kg"` or `"lb"`). Without one Loadpath reads
  the plan as kg, so a `step` left out is 2.5 kg even for a lifter who uses pounds.
- Progression: use Loadpath's rules rather than describing them in words.
  - Barbell main lifts: `linear` (add `step` when every rep lands), `step` left out
    (Loadpath's default, 2.5 kg / 5 lb) or 5 kg / 10 lb on deadlifts and squats.
  - Accessories: `reps` + `repsTo` (that's `double`: reps climb to `repsTo`, then
    `step` is added and reps go back to `reps`). Dumbbell and isolation lifts:
    `step` 1–2 kg / 2.5–5 lb.
  - Bodyweight lifts (pull-ups, push-ups, dips, hanging raises): `reps` + `repsTo`
    and no `step`.
  - Training-max programs (5/3/1): `"rule": "percent"` with `wave`s, and weeks
    carrying `wave` (`"5s"`, `"3s"`, `"531"` or `"deload"`). Supplemental work at a
    flat percent (Boring But Big 5×10 at 50%) is the same lift listed a second time in
    the workout, its sets with `percent` and no `wave`. A lift may appear twice in a
    workout.
  - GZCLP: `"rule": "stages"`.
- Weeks: the days run in order, rest days included, so list all seven days of a week
  with `null` for rest days. A program repeats its `weeks`; one week is enough for a
  plan that doesn't change week to week. A deload week has `"deload": 60` (its weight
  as a percent, 30–95); add `"deloadFewerSets": true` to also drop one set from every lift.
- Write only fields `reference/format.md` describes; Loadpath drops any other.

## 3. Check the plan

Loadpath refuses the whole plan over one value it can't build. Check against
`reference/format.md`, above all:

- `sets`, `reps`, `repsTo`, `rest`, `warmups` and `kcal` are whole numbers: sets 1–20,
  reps 1–100, `rest` 0–3600, `warmups` 0–10.
- A rep range (`repsTo`, or `"rule": "double"`): `reps` ≤ `repsTo` ≤ 60.
- Every `lift` is spelled as in `reference/lifts.md` and written with its kind's fields.
- `setList`: no `sets`, `reps` or `amrap` beside it; at most one `top`, every set after
  it with a `backoff` and none before it; under a rep range, every set that isn't a
  back-off has the same reps.
- `"rule": "percent"`: a `setList` with a `percent` (up to 150) on each set, and no
  `repsTo` or `weight`. A set's `wave` (1–3) needs its `percent`.
- `"rule": "stages"`: `"stages"` is `"t1"`, `"t2"` or `"t3"`, with no `sets`, `reps`,
  `repsTo`, `amrap` or `setList`.
- `groups`: each entry's `group` is a label a lift in that workout uses; `rest` 15–600,
  `rounds` 0–20.
- The program has a `name`, and every day is a workout's `name` or `null`. A week's
  `wave` is `"5s"`, `"3s"`, `"531"` or `"deload"`; `deload` is 30–95 (60, not 0.6), and
  `deloadFewerSets` comes only with it; `autoDeload` is 2–12.

## 4. Build the link

Run this with the plan, as format.md describes:

```python
import base64, json, zlib
raw = json.dumps(plan, separators=(",", ":")).encode()
c = zlib.compressobj(9, zlib.DEFLATED, -15)
link = "https://getloadpath.com/import#z=" + base64.urlsafe_b64encode(c.compress(raw) + c.flush()).decode().rstrip("=")
print(len(link), link)
```

A link over 4,000 characters is too long: give the JSON instead (below).

## 5. Reply

1. The plan in plain words: each workout's lifts with sets × reps, and how it progresses.
   Keep it short.
2. The link, on its own line, as `[Open in Loadpath](<link>)`. It opens the app on an
   iPhone with Loadpath; elsewhere it opens a page that shows the plan and how to get the app.
3. If they don't have Loadpath: it's free on the App Store,
   https://apps.apple.com/app/apple-store/id6764851498?pt=1053933&ct=claude-skill&mt=8

**If you can't run code**, or the link is too long: give the plan's JSON in a code block
and tell the lifter to copy it, then in Loadpath tap Train → + → Import from Text.
Never write a link by hand; it holds compressed data you can't produce reliably without
running code.
