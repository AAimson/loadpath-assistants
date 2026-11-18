# Loadpath plan format, version 1

A workout or a program for [Loadpath](https://getloadpath.com), as JSON. Loadpath opens
it as a preview; nothing is saved until the lifter taps Save.

## Give it to a lifter

- **As text.** They copy it and use Train → + → Import from Text.
- **As a link:** `https://getloadpath.com/import#z=<payload>`, where the payload is the
  JSON, raw-DEFLATE compressed (RFC 1951, no header), then base64url with no `=` padding.
  Without compression, use `#j=<payload>`: the JSON, base64url with no padding. Keep a
  link under 4,000 characters; give a longer plan as text.

```python
import base64, json, zlib
raw = json.dumps(plan, separators=(",", ":")).encode()
c = zlib.compressobj(9, zlib.DEFLATED, -15)
link = "https://getloadpath.com/import#z=" + base64.urlsafe_b64encode(c.compress(raw) + c.flush()).decode().rstrip("=")
```

How a link opens: Loadpath accepts `https://getloadpath.com/import#…` when it is opened in
the app, and `loadpath://import#…` (same payload) opens the app directly. Until the site's
association file and the app's Associated Domains ship, tapping the `https` link opens the
web page rather than the app; use the `loadpath://` form, or give the plan as text. The
payload sits after the `#`, which a browser never sends, so a plan never reaches the
site's server.

## The document

```json
{
  "loadpath": 1,
  "unit": "kg",
  "workouts": [
    {
      "name": "Upper A",
      "lifts": [
        { "lift": "Bench Press", "sets": 3, "reps": 5, "rule": "linear", "step": 2.5, "rest": 180, "warmups": 2 },
        { "lift": "Dumbbell Row", "sets": 3, "reps": 8, "repsTo": 12, "group": "A" },
        { "lift": "Face Pull", "sets": 3, "reps": 12, "repsTo": 15, "group": "A" },
        { "lift": "Dead Hang Hold", "sets": 3, "seconds": 45 },
        { "lift": "Zone 2 Bike", "minutes": 20 }
      ]
    }
  ],
  "program": {
    "name": "Upper / Lower",
    "repeat": 0,
    "weeks": [ { "days": ["Upper A", null, "Lower A", null] } ]
  }
}
```

| Field | Meaning |
|---|---|
| `loadpath` | The format's version: `1` for everything on this page. Loadpath refuses a number it doesn't know and asks the lifter to update. |
| `unit` | `"kg"` or `"lb"`, for every `weight` and `step`. **Required** when the plan has either: Loadpath refuses a weight or a step with no unit rather than guess, and refuses any other unit. |
| `workouts` | One or more, each with a `name` and at least one lift, in order. |
| `program` | Optional. Its `weeks` each list `days`: a workout's `name`, or `null` for a rest day. A day naming a workout that isn't in `workouts` is refused. `repeat` is how many times the weeks run; `0` or absent runs until the lifter ends it. |

A lift:

| Field | Meaning |
|---|---|
| `lift` | The exercise's name. Use Loadpath's name when you know it ("Bench Press", "Romanian Deadlift"); a close spelling is matched, and the lifter is asked about anything else. A lift is matched by name among Loadpath's lifts with the same kind of set (sets × reps, minutes, or seconds): a timed lift only matches a library lift that is timed. |
| `id` | Optional. Loadpath's id for the exercise, when you know it. It never overrides the name unseen: when the two don't agree, the lifter is shown the row to check. |
| `sets`, `reps` | Working sets and reps (the short form; or give `setList`). Required for a strength lift (1–20 sets, 1–100 reps), except under `"rule": "stages"` or `"rule": "percent"`, which are refused with them. For a one-arm or one-leg lift, `reps` are per side. |
| `repsTo` | The top of a rep range: `"reps": 8, "repsTo": 12` is 8–12. |
| `rule` | `"linear"`: add `step` when every rep lands. `"double"`: add reps up to `repsTo`, then add `step` and start again at `reps`. `"none"`: no automatic change. Left out, it is `double` with a `repsTo` and `linear` without. `"percent"`: percent of training max, each set in `setList` gives its `percent`. `"stages"`: a GZCLP tier, with `stages`. |
| `step` | How much weight to add. Left out, Loadpath's default (2.5 kg or 5 lb). |
| `weight` | A starting weight. Leave it out: Loadpath then starts from the lifter's own history. For a lift done with two dumbbells or kettlebells it is the weight of **one**; Loadpath converts for a lifter who counts the pair. |
| `rest` | Seconds between sets, 0–3600. |
| `warmups` | How many warm-up sets Loadpath adds before the working sets, 0–10. |
| `amrap` | `true`: the last set is as many reps as possible. |
| `setList` | Instead of `sets`, `reps` and `amrap`: the working sets one by one (below). |
| `repsOnly` | `true`: logged as reps only, no weight. A lift Loadpath creates for it logs reps only. |
| `group` | Lifts in a workout with the same label are done as a superset (see Supersets and circuits). Lifts in one group are evened out to the same number of sets (the larger count) when saved. |
| `seconds` | A timed exercise: seconds per set, with `sets` (1–20). |
| `minutes`, `km` | A cardio exercise. |
| `kcal` | A cardio lift's calorie target. A whole number. |

### Sets one by one

For a lift the short form can't say, list its working sets in `setList`:

```json
{ "lift": "Squat", "setList": [
  { "reps": 3, "top": true },
  { "reps": 6, "backoff": 15 }, { "reps": 6, "backoff": 15 },
  { "reps": 8, "backoff": 15, "amrap": true, "drops": [8, 6] }
] }
```

| Field | Meaning |
|---|---|
| `reps` | The set's reps, 1–100. Required. |
| `amrap` | `true`: a set to failure. Any number of sets may be. |
| `top` | `true`: the top set. At most one; every set after it is a back-off. |
| `backoff` | Percent lighter than the top set: `10` is 10% less, 0–100. Every set after the top has one, and no set before it. |
| `drops` | The reps of each drop, 1–10 drops. Their weights are worked out when the workout starts. |
| `percent` | Percent of training max, 1–150, under `"rule": "percent"`. |
| `wave` | A 5/3/1 wave position, 1–3, with `percent`: the week's `wave` sets this set's percent, reps and +. |
| `waveReps` | `"own"`: the wave sets the percent only; the set keeps its reps and is never the + set. |
| `seconds` | A timed set's length, 1–3600. |
| `minutes`, `km`, `kcal` | A cardio entry: any of the three. |

A list holds one kind of set: strength sets, timed sets or cardio entries. Timed sets of
different lengths go one by one (`[{"seconds": 30}, {"seconds": 45}]`), and so do several
cardio entries in one exercise (intervals). Use `sets` and `seconds`, or `minutes` and
`km`, when every set is the same.

A lift with `setList` has no `sets`, `reps` or `amrap`. `repsTo` stays on the lift: with
`"rule": "double"`, every set that isn't a back-off has the same reps, the bottom of the
range, and the top set climbs from there. A top set and back-offs suit a strength lift on
`linear`, `double` or `none` that isn't `repsOnly`. Use the short form whenever it says
the same thing.

### Programs on a training max

A lift on `"rule": "percent"` lists its sets in `setList`, each with its `percent` of the
lifter's training max. The training max never travels: the lift arrives with none, and
Loadpath sets it from the lifter's own history when the program starts.

```json
{ "lift": "Back Squat", "rule": "percent", "step": 5, "setList": [
  { "reps": 5, "percent": 65, "wave": 1 }, { "reps": 5, "percent": 75, "wave": 2 },
  { "reps": 5, "percent": 85, "wave": 3, "amrap": true }, { "reps": 10, "percent": 50 }
] }
```

A percent lift takes no `weight`: a weight there is refused, since it would hold the whole
wave at one flat weight until a training max exists. `percent` is any value above 0, up to 150.

`wave`, `deload` and `deloadFewerSets` sit on a week, beside `days`. A week can carry a
5/3/1 `wave` (`"5s"`, `"3s"`, `"531"` or `"deload"`, in any case): it sets the percent,
reps and + of every set with a `wave` that week. A deload week has `"deload": 60` (its
weight as a percent, 30–95) and `"deloadFewerSets": true` to drop a set (`true`
without `deload` is refused). A 5/3/1 deload week carries both `"wave": "deload"` and
`"deload": 60`; in the app, choosing the deload wave also marks the week a deload.
`"autoDeload": 4` on the program adds a deload every 4 weeks (2–12; 0 or absent is off).

```json
{ "name": "Deload", "days": ["Squat Day", null, "Bench Day"], "wave": "deload", "deload": 60, "deloadFewerSets": true }
```

A GZCLP tier is `{ "lift": "Back Squat", "rule": "stages", "stages": "t1" }` with no sets:
Loadpath builds the tier's first stage and steps through its stages from there. The tiers
are Loadpath's own: T1 5×3+, 6×2+, 10×1+; T2 3×10, 3×8, 3×6; T3 3×15+.

### Supersets and circuits

Lifts with the same `group` label are done together. A workout can give a group its own
settings in `groups`; leave a group out and it is a superset with Loadpath's defaults. An entry for a label no lift uses is refused.

```json
"groups": [{ "group": "A", "name": "Arms", "rounds": 3, "rest": 60, "restAfter": "each", "order": "sequential" }]
```

| Field | Meaning |
|---|---|
| `group` | The label its lifts use. |
| `name` | What Loadpath calls the group. |
| `rounds` | Rounds of a circuit, 0–20. 0 or absent: one round per set. Give each lift in a circuit as many sets as `rounds`: a workout runs the sets each lift has. |
| `rest` | Seconds of rest, 15–600. Absent: 90. |
| `restAfter` | `"round"` (after each round, the default), `"each"` (after every lift) or `"none"`. |
| `order` | `"alternate"` (A1, B1, A2, B2, the default) or `"sequential"` (all of A, then all of B). |

Loadpath ignores any field it doesn't know.

### Limits

At most 20 workouts, 40 lifts in a workout and 52 weeks in a program, and the JSON may
inflate to at most 256 KB. A larger plan is refused as too large.

## Versions

A plan that needs something this page doesn't describe is not version 1. Anything that
changes what Loadpath builds gets a new `loadpath` number, so an app that doesn't know it
says "update the app" rather than save a different plan. Write the lowest version that
carries the plan: a version 1 plan opens in every Loadpath that reads plans.

## What Share as Link sends

Share as Link in Loadpath sends every plan Loadpath builds except these, which it refuses
and says why: custom GZCLP stages, a timed exercise with no time set, an exercise with no
sets, more than 20 sets in an exercise, a circuit with more than 20 rounds, more than 10
drops on a set, and a drop with no reps.

Don't add fields this page doesn't describe: an app reading version 1 would drop the
field and save the plan without it. Anything new that changes what is built gets a new
`loadpath` number.

Warm-up sets planned by hand travel as a count in `warmups` (at most 5), since their
weights are the sender's own. Two workouts in a program with the same name go as "Upper"
and "Upper 2".

Share as Link shows what the link says differently from the plan in the app (warm-ups
as a count, a renamed workout, a double-progression lift at the bottom of its range, a
lift that goes outside its group; and, for a session, a lift left out because no working sets were logged for it, and a top set the format can't hold going as plain sets) and a QR code of the link when it fits in one
(2,953 bytes). A finished session shares as one workout, its sets as done.
