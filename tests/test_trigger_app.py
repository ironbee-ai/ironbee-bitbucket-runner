"""The trigger app's released files, as Forge's CLI takes them: the manifest (no app's id, the runtime, exactly the three
scopes, one trigger on a pull request comment's creation, one function, nothing that reaches outside Atlassian, no
storage), package.json pinning @forge/api to one version, and the lockfile holding that same version. The function's
own behaviour is tested by its own tests (trigger-app/test, Node's test runner). Needs PyYAML (skipped without it)."""
from __future__ import annotations

import json
import re
import unittest

from support import ROOT

try:
    import yaml
except ImportError:                                          # pragma: no cover
    yaml = None

APP = ROOT / "trigger-app"
SCOPES = ["read:pullrequest:bitbucket", "read:pipeline:bitbucket", "write:pipeline:bitbucket"]


@unittest.skipIf(yaml is None, "PyYAML is not installed")
class Manifest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = yaml.safe_load((APP / "manifest.yml").read_text())

    def test_no_apps_id_the_setup_registers_one(self):
        self.assertEqual(self.manifest["app"], {"runtime": {"name": "nodejs22.x"}})

    def test_exactly_the_three_scopes_and_nothing_outside_atlassian(self):
        self.assertEqual(self.manifest["permissions"], {"scopes": SCOPES})
        self.assertEqual(list(self.manifest), ["app", "permissions", "modules"])     # no remotes, no egress, no storage

    def test_one_trigger_on_a_comments_creation_and_one_function(self):
        self.assertEqual(self.manifest["modules"], {
            "trigger": [{"key": "ironbee-comment", "function": "on-comment", "events": ["avi:bitbucket:created:pullrequest-comment"]}],
            "function": [{"key": "on-comment", "handler": "index.onComment"}]})

    def test_the_handler_is_the_sources_export(self):
        source = (APP / "src" / "index.js").read_text()
        self.assertRegex(source, r"(?m)^export async function onComment\(event\)")
        self.assertEqual(re.findall(r"(?m)^import .+ from '([^']+)';$", source), ["@forge/api"])    # the one package it reads


class Package(unittest.TestCase):
    def setUp(self) -> None:
        self.package = json.loads((APP / "package.json").read_text())
        self.lock = json.loads((APP / "package-lock.json").read_text())

    def test_forge_api_pinned_to_one_version_and_nothing_else(self):
        self.assertEqual(list(self.package["dependencies"]), ["@forge/api"])
        self.assertRegex(self.package["dependencies"]["@forge/api"], r"^\d+\.\d+\.\d+$")
        self.assertNotIn("devDependencies", self.package)
        self.assertFalse({"preinstall", "install", "postinstall", "prepare"} & set(self.package.get("scripts", {})))   # nothing runs at an install

    def test_the_lockfile_holds_that_version(self):
        pinned = self.package["dependencies"]["@forge/api"]
        self.assertEqual(self.lock["lockfileVersion"], 3)
        self.assertEqual((self.lock["name"], self.lock["version"]), (self.package["name"], self.package["version"]))
        self.assertEqual(self.lock["packages"][""]["dependencies"], self.package["dependencies"])
        self.assertEqual(self.lock["packages"]["node_modules/@forge/api"]["version"], pinned)

    def test_every_locked_package_from_npms_registry_with_its_integrity(self):
        for path, entry in self.lock["packages"].items():
            if not path: continue
            with self.subTest(path):
                self.assertTrue(entry["resolved"].startswith("https://registry.npmjs.org/"), entry["resolved"])
                self.assertTrue(entry["integrity"].startswith("sha512-"))


class TriggerCases(unittest.TestCase):
    def test_the_reviewers_cases_are_there_for_the_apps_tests(self):
        cases = json.loads((APP / "test" / "trigger-cases.json").read_text())["cases"]
        self.assertTrue(cases)
        for case in cases:
            self.assertEqual(set(case), {"raw", "authorType", "addressed", "ours"})


if __name__ == "__main__":
    unittest.main()
