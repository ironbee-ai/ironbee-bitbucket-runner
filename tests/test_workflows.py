"""The build's and the release's workflow files: every action pinned by commit, no expression inside a script, the
build's checks, and the release's inputs through the environment, its steps in order, its one writing job pushing with
the job's own token, and Docker Hub read with the organization's pull token. Needs PyYAML (skipped without it)."""
from __future__ import annotations

import re
import unittest

from support import ROOT

try:
    import yaml
except ImportError:                                          # pragma: no cover
    yaml = None

WORKFLOWS = ROOT / ".github" / "workflows"
BUILD = WORKFLOWS / "build.yml"
RELEASE = WORKFLOWS / "release.yml"
PINNED = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(/[^@]+)?@[0-9a-f]{40}$")
USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s+(\S+)(.*)$")


def load(path) -> dict:
    data = yaml.safe_load(path.read_text())
    data["on"] = data.pop(True, data.get("on"))              # YAML 1.1 reads the key `on` as true
    return data


def strings(node, where=()):
    """Every string in a workflow, with the keys that lead to it."""
    if isinstance(node, dict):
        for k, v in node.items(): yield from strings(v, (*where, str(k)))
    elif isinstance(node, list):
        for i, v in enumerate(node): yield from strings(v, (*where, str(i)))
    elif isinstance(node, str):
        yield where, node


@unittest.skipIf(yaml is None, "PyYAML is not installed")
class Workflows(unittest.TestCase):
    def setUp(self) -> None:
        self.build, self.release = load(BUILD), load(RELEASE)

    def test_every_action_pinned_by_commit_with_its_version(self):
        for path in sorted(WORKFLOWS.glob("*.y*ml")):
            for n, line in enumerate(path.read_text().splitlines(), 1):
                m = USES_LINE.match(line)
                if m:
                    self.assertRegex(m.group(1), PINNED, f"{path.name}:{n}")
                    self.assertRegex(m.group(2), r"^\s+#\s+v\d+(\.\d+)*$", f"{path.name}:{n}")

    def test_no_expression_inside_a_script(self):
        for path, wf in ((BUILD, self.build), (RELEASE, self.release)):
            for where, text in strings(wf):
                if where[-1] == "run": self.assertNotIn("${{", text, f"{path.name}: {'/'.join(where)}")

    def test_the_build(self):
        self.assertEqual(self.build["on"], {"pull_request": {"branches": ["main"]}, "push": {"branches": ["main"]}, "workflow_dispatch": None})
        self.assertEqual(self.build["permissions"], {"contents": "read"})
        self.assertFalse([n for n, j in self.build["jobs"].items() if "permissions" in j])
        runs = "\n".join(s.get("run", "") for j in self.build["jobs"].values() for s in j["steps"])
        for check in ("python -m pytest tests -q", "npm ci --ignore-scripts", "npm test",
                      "shellcheck --shell=bash --external-sources --severity=warning scripts/*.sh", "sha256sum --check --strict", ".github/workflows/*.yml"):
            self.assertIn(check, runs)
        self.assertEqual(self.build["jobs"]["trigger-app"]["defaults"], {"run": {"working-directory": "trigger-app"}})
        [node] = [s for s in self.build["jobs"]["trigger-app"]["steps"] if "actions/setup-node@" in s.get("uses", "")]
        self.assertEqual(node["with"], {"node-version": "22"})                 # the trigger app's Forge runtime

    def test_the_release_takes_its_inputs_through_the_environment(self):
        self.assertEqual(set(self.release["on"]), {"workflow_dispatch"})
        inputs = self.release["on"]["workflow_dispatch"]["inputs"]
        self.assertEqual({k: (v["type"], v["required"]) for k, v in inputs.items()}, {"version": ("string", True), "rc": ("string", False), "digest": ("string", True)})
        self.assertEqual(inputs["rc"]["default"], "")
        self.assertEqual(self.release["env"], {"IRONBEE_VERSION": "${{ inputs.version }}", "IRONBEE_RC": "${{ inputs.rc }}", "IRONBEE_IMAGE_DIGEST": "${{ inputs.digest }}"})
        for where, text in strings(self.release["jobs"]):
            self.assertNotIn("inputs.", text, "/".join(where))

    def test_the_release_runs_its_script_one_step_at_a_time(self):
        runs = [s["run"] for j in self.release["jobs"].values() for s in j["steps"] if "run" in s]
        self.assertEqual(runs, ["bash scripts/release.sh plan", "bash scripts/release.sh digest", "bash scripts/release.sh publish", "bash scripts/release.sh github-release"])
        self.assertEqual(self.release["jobs"]["publish"]["needs"], "plan")
        for job, reads in (("plan", "bash scripts/release.sh digest"), ("publish", "bash scripts/release.sh publish")):
            steps = self.release["jobs"][job]["steps"]
            login = next(i for i, s in enumerate(steps) if "docker/login-action@" in s.get("uses", ""))
            self.assertLess(login, next(i for i, s in enumerate(steps) if s.get("run") == reads), job)   # Docker Hub's tag is read signed in

    def test_the_release_writes_from_its_publishing_job_alone_with_the_jobs_own_token(self):
        self.assertEqual(self.release["permissions"], {"contents": "read"})
        self.assertEqual({n: j.get("permissions") for n, j in self.release["jobs"].items()}, {"plan": None, "publish": {"contents": "write"}})
        self.assertEqual(self.release["concurrency"], {"group": "release", "cancel-in-progress": False})
        for name, job in self.release["jobs"].items():
            [checkout] = [s for s in job["steps"] if "actions/checkout@" in s.get("uses", "")]
            self.assertEqual((checkout["with"]["ref"], checkout["with"]["fetch-depth"]), ("main", 0))
            self.assertEqual(checkout["with"]["persist-credentials"], name == "publish")
            self.assertNotIn("token", checkout["with"])
        [made] = [s for s in self.release["jobs"]["publish"]["steps"] if s.get("run") == "bash scripts/release.sh github-release"]
        self.assertEqual(made["env"], {"GH_TOKEN": "${{ github.token }}"})

    def test_the_release_pulls_with_the_organizations_pull_token(self):
        logins = [s["with"] for j in self.release["jobs"].values() for s in j["steps"] if "docker/login-action@" in s.get("uses", "")]
        self.assertEqual(logins, [{"username": "ironbeeai", "password": "${{ secrets.DOCKERHUB_PULL_TOKEN }}"}] * 2)
        self.assertEqual(set(re.findall(r"secrets\.([A-Za-z0-9_-]+)", RELEASE.read_text())), {"DOCKERHUB_PULL_TOKEN"})
        self.assertNotIn("secrets.", BUILD.read_text())


if __name__ == "__main__":
    unittest.main()
