import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(ROOT, "bin", "pybot-seed-provenance")
STUB = os.path.join(HERE, "stub_runner.py")
FAKE_ROOT = os.path.join(HERE, "fake_pybot")
CORPUS = os.path.join(HERE, "corpus.txt")


def run(args, mode="stable", expect_env=True):
    env = dict(os.environ)
    env["STUB_MODE"] = mode
    command = [sys.executable, TOOL] + args
    return subprocess.run(command, capture_output=True, text=True, env=env)


def base_args(extra=None):
    args = ["--corpus", CORPUS, "--pybot-root", FAKE_ROOT,
            "--runner", "%s %s" % (sys.executable, STUB),
            "--seeds", "0,1,2"]
    return args + (extra or [])


class StableTest(unittest.TestCase):
    def test_stable_exits_zero(self):
        proc = run(base_args())
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_stable_json_is_parseable(self):
        proc = run(base_args(["--json"]))
        report = json.loads(proc.stdout)
        self.assertEqual(report["tool"], "pybot-seed-provenance")
        self.assertEqual(report["summary"]["stability_rate"], 1.0)
        self.assertFalse(report["drift"])

    def test_summary_counts_prompts_and_observations(self):
        report = json.loads(run(base_args(["--json"])).stdout)
        self.assertEqual(report["summary"]["prompts"], 3)   # blank and # lines skipped
        self.assertEqual(report["summary"]["observations"], 9)
        self.assertEqual(report["corpus"]["prompts"], 3)


class DriftTest(unittest.TestCase):
    def test_wording_only_is_reported_as_such(self):
        proc = run(base_args(["--json"]), mode="wording")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report["summary"]["classes"]["wording-only"], 3)
        self.assertEqual(report["summary"]["module_churn_rate"], 0.0)

    def test_module_only_flip_is_not_wording(self):
        report = json.loads(run(base_args(["--json"]), mode="module").stdout)
        self.assertEqual(report["summary"]["classes"]["module-only"], 3)
        self.assertEqual(report["summary"]["wording_only_rate"], 0.0)
        self.assertEqual(report["summary"]["distinct_modules_seen"], 3)

    def test_module_and_text_both_flagged(self):
        report = json.loads(run(base_args(["--json"]), mode="both").stdout)
        self.assertEqual(report["summary"]["classes"]["module-and-text"], 3)

    def test_text_mode_names_the_class(self):
        proc = run(base_args(), mode="wording")
        self.assertIn("wording-only", proc.stdout)
        self.assertIn("wording-only 100.0%", proc.stdout)


class FallbackTest(unittest.TestCase):
    def test_hello_fallback_is_counted(self):
        proc = run(base_args(["--json"]), mode="fallback")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report["summary"]["fallback_hello"], 3)
        self.assertTrue(report["prompts"][0]["fallback_hello"])

    def test_fallback_text_is_visible(self):
        proc = run(base_args(), mode="fallback")
        self.assertIn("fallback", proc.stdout)


class DeterminismTest(unittest.TestCase):
    def test_single_seed_must_reproduce(self):
        try:
            os.remove("/tmp/.pybot-stub-counter")
        except OSError:
            pass
        proc = run(base_args(["--json", "--repeat", "2"]), mode="nondet")
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report["summary"]["repeat_mismatch"], 3)

    def test_repeat_clean_run_stays_zero(self):
        proc = run(base_args(["--json", "--repeat", "2"]))
        self.assertEqual(proc.returncode, 0, proc.stdout[-400:])


class UsageTest(unittest.TestCase):
    def test_missing_corpus_is_usage_error(self):
        proc = run(["--corpus", "/nonexistent/file", "--pybot-root", FAKE_ROOT])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cannot read corpus", proc.stderr)

    def test_empty_corpus_is_usage_error(self):
        path = os.path.join(HERE, "empty.txt")
        with open(path, "w") as handle:
            handle.write("\n# only comments\n")
        proc = run(["--corpus", path, "--pybot-root", FAKE_ROOT])
        self.assertEqual(proc.returncode, 2)

    def test_bad_seeds_is_usage_error(self):
        proc = run(["--corpus", CORPUS, "--pybot-root", FAKE_ROOT, "--seeds", "0,x"])
        self.assertEqual(proc.returncode, 2)

    def test_missing_bot_package_is_usage_error(self):
        proc = run(["--corpus", CORPUS, "--pybot-root", HERE])
        self.assertEqual(proc.returncode, 2)

    def test_desynced_runner_is_usage_error(self):
        proc = run(base_args(), mode="desync")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("module lines", proc.stderr)

    def test_failing_runner_is_usage_error(self):
        proc = run(["--corpus", CORPUS, "--pybot-root", FAKE_ROOT,
                    "--runner", "false"])
        self.assertEqual(proc.returncode, 2)


class ModuleInventoryTest(unittest.TestCase):
    def test_never_seen_modules_come_from_disk(self):
        report = json.loads(run(base_args(["--json"])).stdout)
        self.assertEqual(report["summary"]["module_files_on_disk"], 3)
        self.assertEqual(report["modules_never_seen"], ["arbiter", "smalltalk"])


if __name__ == "__main__":
    unittest.main()