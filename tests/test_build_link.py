"""build_link.py against the app's own verdicts.

    python3 -m unittest discover tests

ACCEPTED and REFUSED mirror the fixtures in fitness-app's FitnessAppTests/PlanDocumentTests.swift,
which run PlanDocument.validated(): when those tests change, change these to match.
"""
import base64
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "build_link.py")
SKILL = os.path.join(ROOT, "plugin", "skills", "loadpath-plans")
CHATGPT = os.path.join(ROOT, "chatgpt")
sys.path.insert(0, os.path.dirname(SCRIPT))
import build_link  # noqa: E402
import make_chatgpt  # noqa: E402


def plan(lift):
    return '{"loadpath":1,"workouts":[{"name":"A","lifts":[' + lift + ']}]}'


def grouped(groups):
    return ('{"loadpath":1,"workouts":[{"name":"A","lifts":[{"lift":"Curl","sets":3,"reps":10,"group":"A"},'
            '{"lift":"Pushdown","sets":3,"reps":12,"group":"A"}],"groups":[' + groups + ']}]}')


def program(fields, week=""):
    return ('{"loadpath":1,"workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}],'
            '"program":{"name":"P",' + fields + '"weeks":[{"days":["A"]' + week + '}]}}')


ACCEPTED = [
    # decodesAWorkoutAndIgnoresFieldsItDoesNotKnow
    '{"loadpath":1,"unit":"lb","futureField":{"a":1},"workouts":[{"name":"Upper","lifts":['
    '{"lift":"Bench Press","id":"bench-press","sets":3,"reps":5,"step":5,"rest":180,"warmups":2,"somethingNew":true},'
    '{"lift":"Dumbbell Row","sets":3,"reps":8,"repsTo":12,"group":"A"}]}]}',
    # aProgramsDaysNameItsWorkoutsAndNullIsRest
    '{"loadpath":1,"workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}],'
    '"program":{"name":"Three Day","repeat":4,"weeks":[{"days":["A",null,"A"]}]}}',
    # aLiftsModeComesFromItsFields
    '{"loadpath":1,"workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5},'
    '{"lift":"Dead Hang Hold","sets":3,"seconds":45},{"lift":"Zone 2 Bike","minutes":20,"km":8}]}]}',
    # aSetListDecodesAndCountsItsSets
    plan('{"lift":"Squat","setList":[{"reps":3,"top":true},{"reps":6,"backoff":15},'
         '{"reps":8,"amrap":true,"backoff":15,"drops":[8,6]}]}'),
    # aBodyweightLiftIsRepsOnly
    plan('{"lift":"Pull-Up","sets":3,"reps":8,"repsOnly":true}'),
    # aSetListUnderDoubleProgressionKeepsOneFloor
    plan('{"lift":"Squat","repsTo":10,"setList":[{"reps":6,"top":true},{"reps":12,"backoff":10}]}'),
    # allowsARepRangeAtTheEditorsBound
    plan('{"lift":"Curl","rule":"double","sets":3,"reps":60}'),
    plan('{"lift":"Curl","sets":3,"reps":8,"repsTo":60}'),
    plan('{"lift":"Curl","rule":"double","setList":[{"reps":60,"top":true},{"reps":100,"backoff":10}]}'),
    # timedAndCardioListsTakeTheirModeFromTheirEntries
    plan('{"lift":"Plank","setList":[{"seconds":30},{"seconds":45},{"seconds":60}]}'),
    plan('{"lift":"Rower","setList":[{"minutes":10,"km":2},{"minutes":5,"kcal":60}]}'),
    plan('{"lift":"Bike","minutes":20,"kcal":200}'),
    plan('{"lift":"Bike","kcal":200}'),
    # aGroupsSettingsDecode
    grouped('{"group":"a","name":"Arms","rounds":3,"rest":60,"restAfter":"each","order":"sequential"}'),
    # aPercentLiftAndAGZCLPTierDecode
    plan('{"lift":"Squat","rule":"percent","setList":[{"reps":5,"percent":65,"wave":1},{"reps":5,"percent":75,"wave":2},'
         '{"reps":5,"percent":85,"wave":3,"amrap":true},{"reps":10,"percent":50},'
         '{"reps":8,"percent":60,"wave":1,"waveReps":"own"}]}'),
    plan('{"lift":"Squat","rule":"stages","stages":"T1"}'),
    # aProgramsWavesDeloadsAndAutomaticDeloadsDecode
    '{"loadpath":1,"workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}],"program":{"name":"P",'
    '"autoDeload":4,"weeks":[{"days":["A"],"wave":"5s"},{"days":["A"],"wave":"deload","deload":60,"deloadFewerSets":true}]}}',
    # theTopOfTheAutoDeloadRangeAndOffAreAccepted
    program('"autoDeload":12,'),
    program('"autoDeload":0,'),
    # aWaveNameIgnoresCase
    program("", ',"wave":"Deload"'),
    # noExtraSetDropIsNotRefusedWithoutADeload
    program("", ',"deloadFewerSets":false'),
    # A timed lift with no "sets" is one set (validated(): `lift.sets ?? 1`).
    plan('{"lift":"Dead Hang","seconds":30}'),
    # A unit's case doesn't matter (`unit?.lowercased()`).
    '{"loadpath":1,"unit":"LB","workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5,"step":5}]}]}',
]

REFUSED = [
    # refusesWhatItCannotUse
    '{"loadpath":2,"workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}]}',
    '{"loadpath":1,"workouts":[]}',
    '{"loadpath":1,"workouts":[{"name":"A","lifts":[]}]}',
    plan('{"lift":"Squat","sets":3}'),
    plan('{"lift":"Squat","sets":300,"reps":5}'),
    plan('{"lift":"Squat","sets":3,"reps":5,"weight":135}'),
    plan('{"lift":"Squat","sets":3,"reps":5,"step":5}'),
    '{"loadpath":1,"unit":"stone","workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}]}',
    '{"loadpath":1,"workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}],'
    '"program":{"name":"P","weeks":[{"days":["B"]}]}}',
    # refusesARestOutOfRangeOnATimedLift
    plan('{"lift":"Plank","sets":3,"seconds":30,"rest":4000}'),
    # refusesAPlanThatIsTooLarge
    plan(",".join(['{"lift":"Squat","sets":3,"reps":5}'] * 41)),
    # refusesARepRangeBeyondTheEditorsBound
    plan('{"lift":"Curl","rule":"double","sets":3,"reps":61}'),
    plan('{"lift":"Curl","sets":3,"reps":8,"repsTo":61}'),
    plan('{"lift":"Curl","rule":"double","setList":[{"reps":61}]}'),
    # refusesASetListTheEditorCouldNotMake
    plan('{"lift":"Squat","sets":3,"reps":5,"setList":[{"reps":5}]}'),
    plan('{"lift":"Squat","reps":5,"setList":[{"reps":5}]}'),
    plan('{"lift":"Squat","amrap":true,"setList":[{"reps":5}]}'),
    plan('{"lift":"Squat","setList":[]}'),
    plan('{"lift":"Squat","setList":[{"top":true}]}'),
    plan('{"lift":"Squat","setList":[{"reps":101}]}'),
    plan('{"lift":"Squat","setList":[{"reps":3,"top":true},{"reps":3,"top":true}]}'),
    plan('{"lift":"Squat","setList":[{"reps":5,"backoff":10}]}'),
    plan('{"lift":"Squat","setList":[{"reps":5,"backoff":10},{"reps":3,"top":true}]}'),
    plan('{"lift":"Squat","setList":[{"reps":3,"top":true},{"reps":5}]}'),
    plan('{"lift":"Squat","setList":[{"reps":3,"top":true,"backoff":10},{"reps":5,"backoff":10}]}'),
    plan('{"lift":"Squat","setList":[{"reps":3,"top":true},{"reps":5,"backoff":101}]}'),
    plan('{"lift":"Dip","repsOnly":true,"setList":[{"reps":3,"top":true},{"reps":5,"backoff":10}]}'),
    plan('{"lift":"Squat","setList":[{"reps":5,"drops":[]}]}'),
    plan('{"lift":"Squat","setList":[{"reps":5,"drops":[0]}]}'),
    plan('{"lift":"Squat","setList":[{"reps":5,"drops":[5,5,5,5,5,5,5,5,5,5,5]}]}'),
    plan('{"lift":"Squat","repsTo":6,"setList":[{"reps":8}]}'),
    plan('{"lift":"Squat","repsTo":10,"setList":[{"reps":6},{"reps":8}]}'),
    plan('{"lift":"Plank","seconds":30,"sets":3,"setList":[{"reps":5}]}'),
    plan('{"lift":"Bike","minutes":20,"setList":[{"reps":5}]}'),
    # refusesMoreSetsInAListThanALiftMayHave
    plan('{"lift":"Squat","setList":[' + ",".join(['{"reps":5}'] * 21) + ']}'),
    # refusesATimedOrCardioListItCannotBuild
    plan('{"lift":"Plank","seconds":30,"setList":[{"seconds":30}]}'),
    plan('{"lift":"Plank","sets":3,"setList":[{"seconds":30}]}'),
    plan('{"lift":"Plank","setList":[{"seconds":0}]}'),
    plan('{"lift":"Plank","setList":[{"seconds":3601}]}'),
    plan('{"lift":"Plank","setList":[{"seconds":30},{"reps":5}]}'),
    plan('{"lift":"Plank","setList":[{"seconds":30},{"minutes":5}]}'),
    plan('{"lift":"Rower","setList":[{"minutes":10},{"seconds":30}]}'),
    plan('{"lift":"Rower","setList":[{"minutes":10,"reps":5}]}'),
    plan('{"lift":"Rower","minutes":10,"setList":[{"minutes":10}]}'),
    plan('{"lift":"Rower","setList":[{"minutes":-1}]}'),
    plan('{"lift":"Rower","setList":[{"km":2},{"amrap":true}]}'),
    plan('{"lift":"Bike","minutes":20,"kcal":-5}'),
    plan('{"lift":"Squat","setList":[{"reps":5},{"reps":5,"seconds":30}]}'),
    # refusesAGroupTheEditorCouldNotSetUp
    grouped('{"group":"B"}'),
    grouped('{"group":"A","rounds":21}'),
    grouped('{"group":"A","rest":10}'),
    grouped('{"group":"A","rest":601}'),
    grouped('{"group":"A","restAfter":"sometimes"}'),
    grouped('{"group":"A","order":"random"}'),
    grouped('{"group":"A"},{"group":"a"}'),
    # refusesAPercentOrStagedLiftItCannotBuild
    plan('{"lift":"Squat","rule":"percent","sets":3,"reps":5}'),
    plan('{"lift":"Squat","rule":"percent","repsTo":8,"setList":[{"reps":5,"percent":65}]}'),
    plan('{"lift":"Squat","rule":"percent","setList":[{"reps":5,"percent":0}]}'),
    plan('{"lift":"Squat","rule":"percent","setList":[{"reps":5,"percent":151}]}'),
    plan('{"lift":"Squat","rule":"percent","setList":[{"reps":5,"wave":1}]}'),
    plan('{"lift":"Squat","rule":"percent","setList":[{"reps":5,"percent":65,"wave":4}]}'),
    plan('{"lift":"Squat","rule":"percent","setList":[{"reps":5,"percent":65,"waveReps":"own"}]}'),
    plan('{"lift":"Squat","rule":"percent","setList":[{"reps":5,"percent":65,"wave":1,"waveReps":"mine"}]}'),
    plan('{"lift":"Squat","rule":"percent","setList":[{"reps":3,"percent":85,"top":true},'
         '{"reps":5,"percent":75,"backoff":10}]}'),
    plan('{"lift":"Squat","rule":"linear","setList":[{"reps":5,"percent":65}]}'),
    plan('{"lift":"Squat","setList":[{"reps":5,"wave":1}]}'),
    plan('{"lift":"Squat","rule":"stages"}'),
    plan('{"lift":"Squat","rule":"stages","stages":"t4"}'),
    plan('{"lift":"Squat","rule":"stages","stages":"t1","sets":5,"reps":3}'),
    plan('{"lift":"Squat","rule":"stages","stages":"t1","setList":[{"reps":3}]}'),
    plan('{"lift":"Squat","rule":"linear","stages":"t1","sets":3,"reps":5}'),
    plan('{"lift":"Plank","seconds":30,"stages":"t1"}'),
    plan('{"lift":"Plank","rule":"percent","seconds":30}'),
    plan('{"lift":"Rower","rule":"stages","minutes":10}'),
    plan('{"lift":"Plank","setList":[{"seconds":30,"percent":65}]}'),
    plan('{"lift":"Rower","setList":[{"minutes":10,"wave":1}]}'),
    plan('{"lift":"Dip","repsOnly":true,"rule":"percent","setList":[{"reps":5,"percent":65}]}'),
    plan('{"lift":"Dip","repsOnly":true,"rule":"stages","stages":"t3"}'),
    # refusesAWeekOrProgramTheEditorCouldNotMake
    program("", ',"wave":"6s"'),
    program("", ',"deload":20'),
    program("", ',"deload":96'),
    program("", ',"deloadFewerSets":true'),
    program('"autoDeload":1,'),
    program('"autoDeload":13,'),
    program('"autoDeload":53,'),
    # aWeightOnAPercentLiftIsRefused
    '{"loadpath":1,"unit":"kg","workouts":[{"name":"A","lifts":[{"lift":"Squat","rule":"percent","weight":100,'
    '"setList":[{"reps":5,"percent":65}]}]}]}',
    # Beyond the Swift fixtures: what validated() and the decoder refuse that an assistant might write.
    program("", ',"wave":"5/3/1"'),
    program("", ',"deload":0.6'),
    '{"loadpath":1,"workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}],"program":{"weeks":[{"days":["A"]}]}}',
    '{"loadpath":1,"workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}],'
    '"program":{"name":"P","weeks":[{"days":[null,null,null]}]}}',
    plan('{"lift":"Push-Up","sets":3,"reps":12,"repsTo":8}'),
    plan('{"lift":"Squat","sets":3,"reps":5,"warmups":12}'),
    plan('{"lift":"Squat","sets":3,"reps":5,"rest":90.5}'),
    plan('{"lift":"Squat","sets":"3","reps":5}'),
    plan('{"lift":"Squat","sets":3,"reps":5,"amrap":"yes"}'),
    plan('{"lift":"Bike","minutes":20,"kcal":150.5}'),
    plan('{"sets":3,"reps":5}'),
    plan('{"lift":"   ","sets":3,"reps":5}'),
    '{"loadpath":1,"workouts":[{"name":" ","lifts":[{"lift":"Squat","sets":3,"reps":5}]}]}',
    '{"loadpath":"1","workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}]}',
    '{"loadpath":1,"unit":"kgs","workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}]}',
    '{"loadpath":1,"workouts":[{"name":"A","lifts":[{"lift":"Squat","sets":3,"reps":5}]}],'
    '"program":{"name":"P","weeks":[{"days":["A", 2]}]}}',
    '[{"loadpath":1}]',
]


def run(text):
    return subprocess.run([sys.executable, SCRIPT], input=text, capture_output=True, text=True)


class AgreesWithTheApp(unittest.TestCase):
    def test_accepted(self):
        for text in ACCEPTED:
            with self.subTest(text=text):
                errors, _ = build_link.check(json.loads(text))
                self.assertEqual(errors, [])

    def test_refused(self):
        for text in REFUSED:
            with self.subTest(text=text):
                errors, _ = build_link.check(json.loads(text))
                self.assertNotEqual(errors, [])


class Warnings(unittest.TestCase):
    def warnings(self, text):
        errors, warnings = build_link.check(json.loads(text))
        self.assertEqual(errors, [])
        return warnings

    def test_a_timed_plank_matches_the_catalogue(self):
        self.assertEqual(self.warnings(plan('{"lift":"Plank","id":"plank","sets":3,"seconds":45}')), [])

    def test_a_plank_by_reps_wont_match(self):
        warnings = self.warnings(plan('{"lift":"Plank","sets":3,"reps":10}'))
        self.assertTrue(any("won't match" in w for w in warnings), warnings)

    def test_a_reps_only_lift_matches_a_strength_lift(self):
        self.assertEqual(self.warnings(plan('{"lift":"Pull-Up","sets":3,"reps":8,"repsOnly":true}')), [])

    def test_no_unit(self):
        [warning] = self.warnings(plan('{"lift":"Bench Press","sets":3,"reps":5}'))
        self.assertIn('"unit"', warning)

    def test_no_unit_on_a_cardio_plan_is_fine(self):
        self.assertEqual(self.warnings(plan('{"lift":"Run","minutes":30}')), [])

    def test_a_rule_word_loadpath_doesnt_know(self):
        warnings = self.warnings('{"loadpath":1,"unit":"kg","workouts":[{"name":"A","lifts":['
                                 '{"lift":"Bench Press","sets":3,"reps":5,"rule":"linear progression"}]}]}')
        self.assertEqual(len(warnings), 1)
        self.assertIn('reads it as "linear"', warnings[0])

    def test_an_unknown_field(self):
        warnings = self.warnings('{"loadpath":1,"unit":"kg","workouts":[{"name":"A","lifts":['
                                 '{"lift":"Bench Press","sets":3,"reps":5,"notes":"pause"}]}]}')
        self.assertEqual(len(warnings), 1)
        self.assertIn('"notes"', warnings[0])

    def test_an_id_that_names_another_lift(self):
        [warning] = self.warnings('{"loadpath":1,"unit":"kg","workouts":[{"name":"A","lifts":['
                                  '{"lift":"Bench Press","id":"back-squat","sets":3,"reps":5}]}]}')
        self.assertIn('"Back Squat"', warning)


class Link(unittest.TestCase):
    PLAN = '{"loadpath":1,"unit":"kg","workouts":[{"name":"A","lifts":[{"lift":"Back Squat","sets":3,"reps":5}]}]}'

    def test_the_link_inflates_to_the_plan(self):
        result = run(self.PLAN)
        self.assertEqual(result.returncode, 0, result.stderr)
        link = result.stdout.strip()
        self.assertTrue(link.startswith(build_link.LINK))
        payload = link[len(build_link.LINK):]
        raw = zlib.decompress(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)), -15)
        self.assertEqual(json.loads(raw), json.loads(self.PLAN))

    def test_a_refused_plan_exits_1(self):
        result = run(plan('{"lift":"Squat","sets":3}'))
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_a_list_is_an_error_not_a_crash(self):
        result = run("[]")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)

    def test_a_long_plan_comes_back_as_json(self):
        catalogue = json.load(open(os.path.join(os.path.dirname(SCRIPT), "lifts.json"), encoding="utf-8"))
        names = [e["name"] for e in catalogue if e["kind"] == "Strength"]
        # Varied enough that it doesn't compress under the limit.
        workouts = [{"name": f"Day {i}", "lifts": [
            {"lift": names[(i * 40 + j) % len(names)], "sets": 1 + (i + j) % 5, "reps": 3 + (i * 7 + j) % 10,
             "repsTo": 13 + (i + j * 3) % 8} for j in range(40)]} for i in range(20)]
        text = json.dumps({"loadpath": 1, "unit": "kg", "workouts": workouts})
        result = run(text)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads(text))


class TheSkillsDocs(unittest.TestCase):
    """The skill ships no script: Claude checks a plan against format.md and builds its link
    with the code in SKILL.md, so both have to be right."""

    def read(self, name):
        with open(os.path.join(SKILL, name), encoding="utf-8") as f:
            return f.read()

    def test_format_examples_are_plans_the_app_takes(self):
        text = self.read("reference/format.md")
        document = re.search(r"## The document\n\n```json\n(.*?)```", text, re.S).group(1)
        self.assertEqual(build_link.check(json.loads(document))[0], [])
        snippets = re.findall(r'```json\n(\{ "lift".*?)```', text, re.S)
        self.assertTrue(snippets)
        for snippet in snippets:
            plan = {"loadpath": 1, "unit": "kg", "workouts": [{"name": "A", "lifts": [json.loads(snippet)]}]}
            self.assertEqual(build_link.check(plan)[0], [], snippet)

    def test_the_skills_link_code_opens_the_plan(self):
        code = re.search(r"```python\n(.*?)```", self.read("SKILL.md"), re.S).group(1)
        plan = json.loads(Link.PLAN)
        scope = {"plan": plan}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(code, scope)
        self.assertEqual(scope["link"], build_link.encode(plan)[1])


class TheChatGPTPlugin(unittest.TestCase):
    """chatgpt/ is written by tools/make_chatgpt.py; a skill edited in plugin/ without
    running it leaves ChatGPT on the old skill."""

    def test_its_skill_is_the_claude_skill_for_chatgpt(self):
        target = os.path.join(CHATGPT, "skills", "loadpath-plans")
        for folder, _, files in os.walk(SKILL):
            for name in files:
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as f:
                    expected = f.read()
                if name == "SKILL.md":
                    expected = make_chatgpt.for_chatgpt(expected)
                copy = os.path.join(target, os.path.relpath(path, SKILL))
                with open(copy, encoding="utf-8") as f:
                    self.assertEqual(f.read(), expected, f"{copy}: run tools/make_chatgpt.py")
        self.assertIn("ct=chatgpt", open(os.path.join(target, "SKILL.md"), encoding="utf-8").read())

    def test_its_manifest_fits_the_portal(self):
        with open(os.path.join(CHATGPT, "plugin.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        with open(os.path.join(ROOT, "plugin", ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            self.assertEqual(manifest["version"], json.load(f)["version"])
        self.assertRegex(manifest["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
        ui = manifest["extensions"]["com.openai"]["interface"]
        for field, limit in [("displayName", 30), ("shortDescription", 30), ("longDescription", 4000),
                             ("developerName", 80)]:
            self.assertTrue(0 < len(ui[field]) <= limit, field)
        for field in ("composerIcon", "logo"):
            self.assertTrue(os.path.isfile(os.path.join(CHATGPT, ui[field])), ui[field])


if __name__ == "__main__":
    unittest.main()
