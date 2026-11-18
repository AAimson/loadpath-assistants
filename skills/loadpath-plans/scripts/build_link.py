#!/usr/bin/env python3
"""Check a Loadpath plan (format version 1) and print the link that opens it.

    python3 build_link.py plan.json      # or pipe the JSON on stdin

Prints the link on stdout. Problems that would make Loadpath refuse the plan are
printed as ERROR and stop the script (exit 1). Lift names Loadpath won't match on
its own are printed as WARNING: the link still works, but the lifter is asked
about each one, so fix them first when a Loadpath lift fits.

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


def norm(name):
    return " ".join(str(name).split()).lower()


def lift_kind(lift):
    """'timed', 'cardio' or 'strength', from the fields the lift carries."""
    entries = lift.get("setList") or []
    if "seconds" in lift or any("seconds" in s for s in entries):
        return "timed"
    cardio = ("minutes", "km", "kcal")
    if any(k in lift for k in cardio) or any(any(k in s for k in cardio) for s in entries):
        return "cardio"
    return "strength"


CATALOGUE_KIND = {"Strength": "strength", "Reps": "strength", "Time": "timed", "Cardio": "cardio"}


def load_catalogue():
    with open(os.path.join(HERE, "lifts.json")) as f:
        lifts = json.load(f)
    by_name = {}
    for entry in lifts:
        for name in [entry["name"]] + entry.get("aliases", []):
            by_name.setdefault(norm(name), entry)
    return lifts, by_name


def check(plan):
    errors, warnings = [], []
    if plan.get("loadpath") != 1:
        errors.append('"loadpath" must be 1.')
    workouts = plan.get("workouts")
    if not isinstance(workouts, list) or not 1 <= len(workouts) <= 20:
        errors.append('"workouts" must be a list of 1 to 20 workouts.')
        return errors, warnings

    lifts, by_name = load_catalogue()
    names = [entry["name"] for entry in lifts]
    ids = {entry["id"]: entry for entry in lifts}
    has_load = False

    for w in workouts:
        wname = w.get("name")
        if not wname:
            errors.append("A workout has no name.")
        ws = w.get("lifts")
        if not isinstance(ws, list) or not 1 <= len(ws) <= 40:
            errors.append(f'Workout "{wname}" needs 1 to 40 lifts.')
            continue
        for lift in ws:
            name = lift.get("lift")
            where = f'"{name}" in "{wname}"'
            if not name:
                errors.append(f'A lift in "{wname}" has no "lift" name.')
                continue
            has_load = has_load or "weight" in lift or "step" in lift
            kind = lift_kind(lift)
            rule = lift.get("rule")
            if kind == "strength":
                if rule == "stages":
                    if any(k in lift for k in ("sets", "reps", "setList")):
                        errors.append(f'{where}: "rule": "stages" takes no sets, reps or setList.')
                elif rule == "percent":
                    if "setList" not in lift or "sets" in lift or "reps" in lift:
                        errors.append(f'{where}: "rule": "percent" needs setList (each set with percent) and no sets or reps.')
                    if "weight" in lift:
                        errors.append(f'{where}: a percent lift takes no weight.')
                elif "setList" in lift:
                    if any(k in lift for k in ("sets", "reps", "amrap")):
                        errors.append(f'{where}: a lift with setList has no sets, reps or amrap.')
                else:
                    sets, reps = lift.get("sets"), lift.get("reps")
                    if not isinstance(sets, int) or not 1 <= sets <= 20:
                        errors.append(f'{where}: "sets" must be 1 to 20.')
                    if not isinstance(reps, int) or not 1 <= reps <= 100:
                        errors.append(f'{where}: "reps" must be 1 to 100.')
            elif kind == "timed" and "setList" not in lift:
                if not isinstance(lift.get("sets"), int) or not 1 <= lift["sets"] <= 20:
                    errors.append(f'{where}: a timed lift needs "sets" (1 to 20) with "seconds".')

            entry = by_name.get(norm(name))
            if entry is None:
                close = difflib.get_close_matches(name, names, n=3, cutoff=0.6)
                hint = f" Closest Loadpath lifts: {', '.join(close)}." if close else ""
                warnings.append(f"{where} is not a Loadpath lift name; the lifter will be asked to match it.{hint}")
            elif CATALOGUE_KIND[entry["kind"]] != kind:
                warnings.append(f'{where}: Loadpath\'s "{entry["name"]}" is {CATALOGUE_KIND[entry["kind"]]}, '
                                f"but this lift is written as {kind}; it won't match.")
            if "id" in lift:
                by_id = ids.get(lift["id"])
                if by_id is None:
                    warnings.append(f'{where}: no Loadpath lift has the id "{lift["id"]}". Leave "id" out or fix it.')
                elif entry is not None and by_id is not entry:
                    warnings.append(f'{where}: the id "{lift["id"]}" is "{by_id["name"]}", not this name; '
                                    "the lifter will be asked to check it.")

    if has_load and plan.get("unit") not in ("kg", "lb"):
        errors.append('The plan has a weight or step, so "unit" must be "kg" or "lb".')

    program = plan.get("program")
    if program is not None:
        weeks = program.get("weeks")
        if not isinstance(weeks, list) or not 1 <= len(weeks) <= 52:
            errors.append('"program.weeks" must be a list of 1 to 52 weeks.')
        else:
            known = {norm(w.get("name", "")) for w in workouts}
            for i, week in enumerate(weeks, 1):
                for day in week.get("days", []):
                    if day is not None and norm(day) not in known:
                        errors.append(f'Week {i} names "{day}", which is not a workout in "workouts".')
                if week.get("deloadFewerSets") and "deload" not in week:
                    errors.append(f'Week {i}: "deloadFewerSets" needs "deload".')
    return errors, warnings


def encode(plan):
    raw = json.dumps(plan, separators=(",", ":"), ensure_ascii=False).encode()
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return raw, LINK + base64.urlsafe_b64encode(c.compress(raw) + c.flush()).decode().rstrip("=")


def main():
    text = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
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
