#!/usr/bin/env python3
"""Check a Loadpath plan (format version 1) and print the link that opens it.

    python3 build_link.py plan.json      # or pipe the JSON on stdin

Prints the link on stdout. Problems that would make Loadpath refuse the plan are
printed as ERROR and stop the script (exit 1): the checks are the app's own
(PlanDocument.validated() and its JSON decoding). WARNING lines are plans Loadpath
takes but reads differently from what was likely meant: a lift name it won't match
on its own, a field it drops, a rule word it doesn't know, no unit.

A plan whose link would pass 4,000 characters is printed as compact JSON instead
(exit 2), for the lifter to paste into Train → + → Import from Text.
"""
import base64
import difflib
import json
import os
import sys
import zlib

LINK = "https://getloadpath.com/import#z="
MAX_LINK = 4000
MAX_INFLATED = 256 * 1024

HERE = os.path.dirname(os.path.abspath(__file__))

# What the app decodes, field by field (PlanDocument's Codable types). A value of the
# wrong type, or a missing required field, makes the whole plan unreadable.
INT, NUM, BOOL, STR = "a whole number", "a number", "true or false", "text"
SCHEMA = {
    "plan": {"loadpath": INT, "unit": STR, "workouts": ["workout"], "program": "program"},
    "workout": {"name": STR, "lifts": ["lift"], "groups": ["group"]},
    "lift": {"lift": STR, "id": STR, "sets": INT, "reps": INT, "repsTo": INT, "rule": STR, "step": NUM,
             "weight": NUM, "rest": INT, "warmups": INT, "amrap": BOOL, "group": STR, "seconds": NUM,
             "minutes": NUM, "km": NUM, "kcal": INT, "setList": ["set"], "repsOnly": BOOL, "stages": STR},
    "set": {"reps": INT, "amrap": BOOL, "top": BOOL, "backoff": NUM, "drops": [INT], "seconds": NUM,
            "minutes": NUM, "km": NUM, "kcal": INT, "percent": NUM, "wave": INT, "waveReps": STR},
    "group": {"group": STR, "name": STR, "rounds": INT, "rest": INT, "restAfter": STR, "order": STR},
    "program": {"name": STR, "detail": STR, "repeat": INT, "weeks": ["week"], "autoDeload": INT},
    "week": {"name": STR, "days": ["day"], "wave": STR, "deload": NUM, "deloadFewerSets": BOOL},
}
REQUIRED = {"plan": ["loadpath", "workouts"], "workout": ["name", "lifts"], "lift": ["lift"], "set": [],
            "group": ["group"], "program": ["name", "weeks"], "week": ["days"]}

RULES = ("linear", "double", "none", "percent", "stages")
CARDIO = ("minutes", "km", "kcal")
CATALOGUE_KIND = {"Strength": "strength", "Reps": "strength", "Time": "timed", "Cardio": "cardio"}
SHAPE = {"strength": "strength", "reps": "strength", "time": "timed", "cardio": "cardio"}


def norm(name):
    return str(name).strip().lower()


def has(d, key):
    return d.get(key) is not None


def get(d, key, default):
    value = d.get(key)
    return default if value is None else value


def as_list(value):
    return value if isinstance(value, list) else []


def rule_of(lift):
    """The app's progressionRule: an unknown word falls back like an absent one."""
    rule = str(get(lift, "rule", "")).lower()
    if rule in RULES:
        return rule
    return "double" if has(lift, "repsTo") else "linear"


def mode_of(lift):
    """The app's mode: a set list's kind is its first entry's."""
    first = (as_list(lift.get("setList")) or [{}])[0]
    first = first if isinstance(first, dict) else {}
    if any(has(lift, k) or has(first, k) for k in CARDIO):
        return "cardio"
    if has(lift, "seconds") or has(first, "seconds"):
        return "time"
    return "reps" if lift.get("repsOnly") is True else "strength"


def objects(plan):
    """Every object in the plan with its kind and a name for messages."""
    yield "plan", plan, "The plan"
    for w in as_list(plan.get("workouts")):
        if not isinstance(w, dict):
            continue
        wn = f'Workout "{w.get("name")}"'
        yield "workout", w, wn
        for g in as_list(w.get("groups")):
            if isinstance(g, dict):
                yield "group", g, f'{wn}, group "{g.get("group")}"'
        for lift in as_list(w.get("lifts")):
            if not isinstance(lift, dict):
                continue
            ln = f'"{lift.get("lift")}" in "{w.get("name")}"'
            yield "lift", lift, ln
            for i, s in enumerate(as_list(lift.get("setList")), 1):
                if isinstance(s, dict):
                    yield "set", s, f"{ln}, set {i}"
    program = plan.get("program")
    if isinstance(program, dict):
        yield "program", program, "The program"
        for i, week in enumerate(as_list(program.get("weeks")), 1):
            if isinstance(week, dict):
                yield "week", week, f"Week {i}"


def unknown_fields(plan):
    """Fields Loadpath doesn't read: it would drop them, so the plan saves without them."""
    return [f'{where}: "{k}" is not a Loadpath field; Loadpath would drop it.'
            for kind, obj, where in objects(plan) for k in obj if k not in SCHEMA[kind]]


def type_ok(value, spec):
    if spec == INT:
        return type(value) is int
    if spec == NUM:
        return type(value) in (int, float)
    if spec == BOOL:
        return type(value) is bool
    if spec == STR:
        return type(value) is str
    return isinstance(value, dict)  # a nested object


def type_errors(plan):
    """What the app's JSON decoding refuses. Any of these and it reads no plan at all."""
    errors = []
    for kind, obj, where in objects(plan):
        for key in REQUIRED[kind]:
            if not has(obj, key):
                errors.append(f'{where}: "{key}" is missing.')
        for key, spec in SCHEMA[kind].items():
            value = obj.get(key)
            if value is None:
                continue
            if isinstance(spec, list):
                item = spec[0]
                if not isinstance(value, list):
                    errors.append(f'{where}: "{key}" must be a list.')
                elif item == "day":
                    if any(d is not None and type(d) is not str for d in value):
                        errors.append(f'{where}: "{key}" holds workout names or null.')
                elif any(not type_ok(v, item) for v in value):
                    errors.append(f'{where}: every item in "{key}" must be '
                                  f'{item if item in (INT, NUM) else "an object"}.')
            elif not type_ok(value, spec):
                errors.append(f'{where}: "{key}" must be {spec if spec != "program" else "an object"}.')
    return errors


def strength_list_problems(entries, lift, rule):
    p = []
    if not 1 <= len(entries) <= 20:
        p.append('"setList" must have 1 to 20 sets.')
    if any(has(s, k) for s in entries for k in ("seconds",) + CARDIO):
        p.append('a sets × reps list can\'t have "seconds", "minutes", "km" or "kcal" in it.')
    for i, s in enumerate(entries, 1):
        if not 1 <= get(s, "reps", 0) <= 100:
            p.append(f'set {i}: "reps" must be 1 to 100.')
        if has(s, "drops") and not (1 <= len(s["drops"]) <= 10 and all(1 <= d <= 100 for d in s["drops"])):
            p.append(f'set {i}: "drops" must be 1 to 10 drops, each 1 to 100 reps.')
        if has(s, "percent") and not (rule == "percent" and 0 < s["percent"] <= 150):
            p.append(f'set {i}: "percent" must be above 0 and at most 150, under "rule": "percent".')
        if has(s, "wave") and not (rule == "percent" and has(s, "percent") and 1 <= s["wave"] <= 3):
            p.append(f'set {i}: "wave" must be 1, 2 or 3, on a set with a "percent", under "rule": "percent".')
        if has(s, "waveReps") and not (has(s, "wave") and s["waveReps"].lower() == "own"):
            p.append(f'set {i}: "waveReps" can only be "own", on a set with a "wave".')
    tops = [i for i, s in enumerate(entries) if s.get("top") is True]
    if len(tops) > 1:
        p.append('only one set can be the "top" set.')
    elif tops:
        if lift.get("repsOnly") is True or rule not in ("linear", "double", "none"):
            p.append('a top set needs a weighted lift on "linear", "double" or "none".')
        for i, s in enumerate(entries):
            if i > tops[0] and not (has(s, "backoff") and 0 <= s["backoff"] <= 100):
                p.append(f'set {i + 1}: every set after the top set needs a "backoff" of 0 to 100.')
            elif i <= tops[0] and has(s, "backoff"):
                p.append(f'set {i + 1}: only sets after the top set take a "backoff".')
    elif any(has(s, "backoff") for s in entries):
        p.append('a "backoff" needs a "top" set before it.')
    floors = {s["reps"] for s in entries if not has(s, "backoff") and has(s, "reps")}
    if rule == "double" and len(floors) > 1:
        p.append('under double progression (a "repsTo" or "rule": "double"), every set that isn\'t a '
                 'back-off has the same reps, the bottom of the range.')
    if has(lift, "repsTo") and not (lift["repsTo"] <= 100 and all(f <= lift["repsTo"] for f in floors)):
        p.append('"repsTo" must be at least every set\'s reps, and at most 100.')
    return p


def timed_list_problems(entries):
    p = []
    if not 1 <= len(entries) <= 20:
        p.append('"setList" must have 1 to 20 sets.')
    for i, s in enumerate(entries, 1):
        if not 1 <= get(s, "seconds", 0) <= 3600:
            p.append(f'set {i}: "seconds" must be 1 to 3600.')
        extra = [k for k in SCHEMA["set"] if k != "seconds" and has(s, k)]
        if extra:
            p.append(f'set {i}: a timed set has only "seconds", not {", ".join(extra)}.')
    return p


def cardio_list_problems(entries):
    p = []
    if not 1 <= len(entries) <= 20:
        p.append('"setList" must have 1 to 20 entries.')
    for i, s in enumerate(entries, 1):
        if not any(has(s, k) for k in CARDIO):
            p.append(f'entry {i}: a cardio entry needs "minutes", "km" or "kcal".')
        if any(get(s, k, 0) < 0 for k in CARDIO):
            p.append(f'entry {i}: "minutes", "km" and "kcal" can\'t be negative.')
        extra = [k for k in SCHEMA["set"] if k not in CARDIO and has(s, k)]
        if extra:
            p.append(f'entry {i}: a cardio entry has only "minutes", "km" and "kcal", not {", ".join(extra)}.')
    return p


def lift_problems(lift):
    """PlanDocument.validated()'s checks on one lift."""
    p = []
    rule, mode = rule_of(lift), mode_of(lift)
    if not 0 <= get(lift, "rest", 0) <= 3600:
        p.append('"rest" must be 0 to 3600 seconds.')
    if mode != "strength" and (has(lift, "stages") or rule in ("percent", "stages")):
        p.append('"rule": "percent" or "stages" needs a weighted sets × reps lift, '
                 'not a timed, cardio or reps-only one.')
    if mode == "cardio":
        if any(get(lift, k, 0) < 0 for k in CARDIO):
            p.append('"minutes", "km" and "kcal" can\'t be negative.')
        if has(lift, "setList"):
            if any(has(lift, k) for k in CARDIO + ("sets",)):
                p.append('with "setList", "minutes", "km" and "kcal" go on its entries, and there is no "sets".')
            p += cardio_list_problems(lift["setList"])
    elif mode == "time":
        if has(lift, "setList"):
            if has(lift, "seconds") or has(lift, "sets"):
                p.append('with "setList", "seconds" goes on its sets, and there is no "sets".')
            p += timed_list_problems(lift["setList"])
        else:
            if not get(lift, "seconds", 0) > 0:
                p.append('"seconds" must be more than 0.')
            if not 1 <= get(lift, "sets", 1) <= 20:
                p.append('"sets" must be 1 to 20.')
    else:
        if get(lift, "weight", 0) < 0 or get(lift, "step", 0) < 0:
            p.append('"weight" and "step" can\'t be negative.')
        if not 0 <= get(lift, "warmups", 0) <= 10:
            p.append('"warmups" must be 0 to 10.')
        if has(lift, "stages") or rule == "stages":
            if rule != "stages":
                p.append('"stages" needs "rule": "stages".')
            if get(lift, "stages", "").lower() not in ("t1", "t2", "t3"):
                p.append('"rule": "stages" needs "stages": "t1", "t2" or "t3".')
            if any(has(lift, k) for k in ("sets", "reps", "amrap", "repsTo", "setList")):
                p.append('a GZCLP tier has no "sets", "reps", "amrap", "repsTo" or "setList": '
                         'Loadpath builds its stages.')
            return p
        if rule == "percent":
            if not has(lift, "setList"):
                p.append('"rule": "percent" needs a "setList", each set with its "percent".')
            if has(lift, "repsTo"):
                p.append('a percent lift has no "repsTo".')
            if has(lift, "weight"):
                p.append('a percent lift has no "weight": Loadpath sets a training max from the lifter\'s history.')
        if has(lift, "setList"):
            if any(has(lift, k) for k in ("sets", "reps", "amrap")):
                p.append('a lift with "setList" has no "sets", "reps" or "amrap".')
            p += strength_list_problems(lift["setList"], lift, rule)
        else:
            sets, reps = lift.get("sets"), lift.get("reps")
            if sets is None or not 1 <= sets <= 20:
                p.append('"sets" must be 1 to 20.')
            if reps is None or not 1 <= reps <= 100:
                p.append('"reps" must be 1 to 100.')
            elif not reps <= get(lift, "repsTo", reps) <= 100:
                p.append('"repsTo" must be from "reps" up to 100.')
        if rule == "double":
            if has(lift, "setList"):
                floors = [s["reps"] for s in lift["setList"] if not has(s, "backoff") and has(s, "reps")]
            else:
                floors = [get(lift, "reps", 0)]
            if any(f > 60 for f in floors) or get(lift, "repsTo", 0) > 60:
                p.append('under double progression (a "repsTo" or "rule": "double"), "reps" and "repsTo" '
                         'are at most 60, where the app\'s rep range stops.')
    return p


def group_problems(group, labels, seen):
    p = []
    label = norm(group["group"])
    if not label or label not in labels:
        p.append("no lift in the workout has this group label.")
    elif label in seen:
        p.append("the workout has two entries for this group.")
    seen.add(label)
    if not 0 <= get(group, "rounds", 0) <= 20:
        p.append('"rounds" must be 0 to 20.')
    if not 15 <= get(group, "rest", 90) <= 600:
        p.append('"rest" must be 15 to 600 seconds.')
    if get(group, "restAfter", "round").lower() not in ("round", "each", "none"):
        p.append('"restAfter" must be "round", "each" or "none".')
    if get(group, "order", "alternate").lower() not in ("alternate", "sequential"):
        p.append('"order" must be "alternate" or "sequential".')
    return p


def plan_errors(plan):
    """PlanDocument.validated(), on a plan whose types decode."""
    errors = []
    if plan["loadpath"] != 1:
        errors.append('"loadpath" must be 1.')
    workouts = plan["workouts"]
    lifts = [lift for w in workouts for lift in w["lifts"]]
    unit = plan.get("unit")
    if unit is not None and unit.lower() not in ("kg", "lb"):
        errors.append('"unit" must be "kg" or "lb".')
    elif unit is None and any(get(l, "weight", 0) > 0 or get(l, "step", 0) > 0 for l in lifts):
        errors.append('The plan has a weight or step, so "unit" must be "kg" or "lb".')
    if not 1 <= len(workouts) <= 20:
        errors.append('"workouts" must have 1 to 20 workouts.')

    for w in workouts:
        wname = w["name"]
        if not wname.strip():
            errors.append("A workout has no name.")
        if not 1 <= len(w["lifts"]) <= 40:
            errors.append(f'Workout "{wname}" needs 1 to 40 lifts.')
        labels = {norm(l["group"]) for l in w["lifts"] if has(l, "group")}
        seen = set()
        for g in as_list(w.get("groups")):
            errors += [f'Workout "{wname}", group "{g["group"]}": {p}' for p in group_problems(g, labels, seen)]
        for lift in w["lifts"]:
            if not lift["lift"].strip():
                errors.append(f'A lift in "{wname}" has no "lift" name.')
                continue
            errors += [f'"{lift["lift"]}" in "{wname}": {p}' for p in lift_problems(lift)]

    program = plan.get("program")
    if program is not None:
        weeks = program["weeks"]
        if not program["name"].strip():
            errors.append("The program has no name.")
        if not 1 <= len(weeks) <= 52:
            errors.append('"program.weeks" must have 1 to 52 weeks.')
        if not any(d is not None for week in weeks for d in week["days"]):
            errors.append("The program has no workout on any day.")
        known = {norm(w["name"]) for w in workouts}
        for i, week in enumerate(weeks, 1):
            for day in week["days"]:
                if day is not None and norm(day) not in known:
                    errors.append(f'Week {i} names "{day}", which is not a workout in "workouts".')
            if has(week, "wave") and week["wave"].lower() not in ("5s", "3s", "531", "deload"):
                errors.append(f'Week {i}: "wave" must be "5s", "3s", "531" or "deload".')
            if has(week, "deload") and not 30 <= week["deload"] <= 95:
                errors.append(f'Week {i}: "deload" is the week\'s weight as a percent, 30 to 95 (60, not 0.6).')
            if week.get("deloadFewerSets") is True and not has(week, "deload"):
                errors.append(f'Week {i}: "deloadFewerSets" needs "deload".')
        if get(program, "autoDeload", 0) != 0 and not 2 <= program["autoDeload"] <= 12:
            errors.append('"autoDeload" must be 2 to 12 weeks, or 0 for none.')
    return errors


def load_catalogue():
    with open(os.path.join(HERE, "lifts.json"), encoding="utf-8") as f:
        lifts = json.load(f)
    by_name = {}
    for entry in lifts:
        for name in [entry["name"]] + entry.get("aliases", []):
            by_name.setdefault(norm(name), entry)
    return lifts, by_name


def plan_warnings(plan):
    """What Loadpath takes but reads differently from what was likely meant."""
    warnings = []
    lifts, by_name = load_catalogue()
    names = [entry["name"] for entry in lifts]
    ids = {entry["id"]: entry for entry in lifts}
    all_lifts = [(w["name"], lift) for w in plan["workouts"] for lift in w["lifts"]]
    if not has(plan, "unit") and any(mode_of(lift) == "strength" for _, lift in all_lifts):
        warnings.append('The plan has no "unit", so Loadpath reads it as kg and a step left out is 2.5 kg. '
                        'Add "unit": "kg" or "lb".')
    for wname, lift in all_lifts:
        name = lift["lift"]
        where = f'"{name}" in "{wname}"'
        if has(lift, "rule") and lift["rule"].lower() not in RULES:
            warnings.append(f'{where}: "rule": "{lift["rule"]}" is not a Loadpath rule; Loadpath reads it as '
                            f'"{rule_of(lift)}". Use one of {", ".join(RULES)}.')
        kind = SHAPE[mode_of(lift)]
        entry = by_name.get(norm(name))
        if entry is None:
            close = difflib.get_close_matches(name, names, n=3, cutoff=0.6)
            hint = f" Closest Loadpath lifts: {', '.join(close)}." if close else ""
            warnings.append(f"{where} is not a Loadpath lift name; the lifter will be asked to match it.{hint}")
        elif CATALOGUE_KIND[entry["kind"]] != kind:
            warnings.append(f'{where}: Loadpath\'s "{entry["name"]}" is {CATALOGUE_KIND[entry["kind"]]}, '
                            f"but this lift is written as {kind}; it won't match.")
        if has(lift, "id"):
            by_id = ids.get(lift["id"])
            if by_id is None:
                warnings.append(f'{where}: no Loadpath lift has the id "{lift["id"]}". Leave "id" out or fix it.')
            elif entry is not None and by_id is not entry:
                warnings.append(f'{where}: the id "{lift["id"]}" is "{by_id["name"]}", not this name; '
                                "the lifter will be asked to check it.")
    return warnings


def check(plan):
    if not isinstance(plan, dict):
        return ['The plan must be a JSON object: {"loadpath": 1, "workouts": [...]}.'], []
    warnings = unknown_fields(plan)
    errors = type_errors(plan)
    if errors:
        return errors, warnings
    errors = plan_errors(plan)
    return errors, warnings + plan_warnings(plan)


def encode(plan):
    raw = json.dumps(plan, separators=(",", ":"), ensure_ascii=False).encode()
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return raw, LINK + base64.urlsafe_b64encode(c.compress(raw) + c.flush()).decode().rstrip("=")


def main():
    text = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    try:
        plan = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"ERROR: not valid JSON: {e}", file=sys.stderr)
        return 1
    errors, warnings = check(plan)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    if errors:
        return 1
    raw, link = encode(plan)
    if len(raw) > MAX_INFLATED:
        print("ERROR: the plan is over 256 KB; Loadpath refuses it. Split it up.", file=sys.stderr)
        return 1
    if len(link) > MAX_LINK:
        print(f"NOTE: the link would be {len(link)} characters (limit {MAX_LINK}). "
              "Give the lifter this JSON for Train → + → Import from Text instead:", file=sys.stderr)
        print(raw.decode())
        return 2
    print(link)
    return 0


if __name__ == "__main__":
    sys.exit(main())
