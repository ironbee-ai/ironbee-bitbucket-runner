"""What the tests share. A script runs with bash as the release workflow runs it, its environment given whole, with the
stubs first on PATH: `docker` (a registry), `gh` (GitHub's releases of ironbee-ai/ironbee-bitbucket-runner) and `sleep`
(records the pause, waits none). git is the machine's own, against a local origin. No network."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
STUBS = ROOT / "tests" / "stubs"

REPO = "ironbee-ai/ironbee-bitbucket-runner"
TOKEN = "job-token"                                         # the release workflow's own token
TEMPLATE = "templates/bitbucket-pipelines.yml"
RELEASE = "release.json"
TRIGGER_APP = ["trigger-app/manifest.yml", "trigger-app/package.json", "trigger-app/package-lock.json", "trigger-app/src/index.js"]
IMAGE = "docker.io/ironbeeai/ironbee-code-review-runner"


def github() -> dict:
    """The stub GitHub's state: the repository, with no release yet."""
    return {"repo": REPO, "tokens": {TOKEN: "github-actions"}, "releases": {}, "fail": [], "next_id": 1000}


@dataclass
class Ran:
    code: int
    out: str
    err: str
    calls: list            # the stub gh's calls, in order
    state: dict            # the stub GitHub after the run
    sleeps: list           # the pauses asked for

    def writes(self) -> list:
        return [c for c in self.calls if c["method"] != "GET"]


class ScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ironbee-scripts-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = github()

    def run_script(self, script: str, env: dict | None = None, args: tuple = (), cwd: Path | None = None) -> Ran:
        """`cwd`: where the script runs, the test's own directory when not given."""
        files = {k: self.tmp / k for k in ("state.json", "calls.jsonl", "sleeps")}
        files["state.json"].write_text(json.dumps(self.state))
        for k in ("calls.jsonl", "sleeps"): files[k].write_text("")
        e = {"PATH": f"{STUBS}{os.pathsep}{os.environ['PATH']}", "HOME": str(self.tmp), "TMPDIR": str(self.tmp),
             "STUB_GH_STATE": str(files["state.json"]), "STUB_GH_CALLS": str(files["calls.jsonl"]), "STUB_SLEEP_LOG": str(files["sleeps"]),
             "GITHUB_REPOSITORY": REPO, "GH_TOKEN": TOKEN}
        e.update(env or {})
        p = subprocess.run(["bash", str(SCRIPTS / script), *args], env={k: v for k, v in e.items() if v is not None}, capture_output=True, text=True, timeout=120,
                           cwd=cwd or self.tmp)
        calls = [json.loads(line) for line in files["calls.jsonl"].read_text().splitlines() if line]
        return Ran(p.returncode, p.stdout, p.stderr, calls, json.loads(files["state.json"].read_text()), files["sleeps"].read_text().split())
