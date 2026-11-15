"""The block's template and release.json: the block parsed with every one of its fixed names (the custom pipeline, its
one step and the two triggers that name it), the release's name read from the comment on the pipeline's line, the image
by digest, and release.json's shape, its values agreeing with the template's. Before the first release both hold their
placeholders; after it, the release's values. Needs PyYAML (skipped without it)."""
from __future__ import annotations

import json
import re
import unittest

from support import IMAGE, RELEASE, ROOT, TEMPLATE, TRIGGER_APP

try:
    import yaml
except ImportError:                                          # pragma: no cover
    yaml = None

PIPELINE = "ironbee-code-review"
SCOPES = ["read:pullrequest:bitbucket", "write:pullrequest:bitbucket", "read:repository:bitbucket", "read:git:bitbucket"]
TRIGGERS = ["pullrequest-created", "pullrequest-updated"]
NAME = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-rc\.[1-9][0-9]*)?")
DIGEST_IMAGE = re.compile(rf"{re.escape(IMAGE)}@sha256:[0-9a-f]{{64}}")
RELEASE_COMMENT = re.compile(r"^    ironbee-code-review:\s+# IronBee's code review, release (\S+)$", re.M)


def release_named(text: str) -> str | None:
    """The release the template's comment names, read from the comment on the pipeline's line."""
    found = RELEASE_COMMENT.findall(text)
    return found[0] if len(found) == 1 else None


@unittest.skipIf(yaml is None, "PyYAML is not installed")
class Template(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (ROOT / TEMPLATE).read_text()
        self.block = yaml.safe_load(self.text)
        self.release = json.loads((ROOT / RELEASE).read_text())

    def step(self) -> dict:
        [entry] = self.block["pipelines"]["custom"][PIPELINE]
        self.assertEqual(list(entry), ["step"])
        return entry["step"]

    def test_the_block_is_the_custom_pipeline_and_its_two_triggers_alone(self):
        self.assertEqual(list(self.block), ["pipelines", "triggers"])
        self.assertEqual(list(self.block["pipelines"]), ["custom"])
        self.assertEqual(list(self.block["pipelines"]["custom"]), [PIPELINE])

    def test_the_step(self):
        step = self.step()
        self.assertEqual(list(step), ["name", "image", "max-time", "concurrency-group", "clone", "auth", "script"])
        self.assertEqual(step["name"], "IronBee Code Review")
        self.assertEqual(step["max-time"], 120)
        self.assertEqual(step["concurrency-group"], "ironbee-code-review-${{BITBUCKET_PR_ID}}")
        self.assertEqual(step["clone"], {"enabled": False})
        self.assertEqual(step["auth"], {"system": {"scopes": SCOPES}})
        self.assertEqual(step["script"], ["ironbee-runner"])

    def test_the_image_by_digest_pulled_with_the_registry_token(self):
        image = self.step()["image"]
        self.assertEqual(list(image), ["name", "username", "password"])
        self.assertEqual((image["username"], image["password"]), ("ironbeeai", "$IRONBEE_REGISTRY_TOKEN"))
        self.assertTrue(image["name"] == "__IRONBEE_IMAGE__" or DIGEST_IMAGE.fullmatch(image["name"]), image["name"])

    def test_the_runs_on_line_is_a_comment_until_a_setup_writes_it(self):
        self.assertNotIn("runs-on", self.step())
        self.assertRegex(self.text, r"(?m)^          # runs-on: \[self\.hosted, linux\]")

    def test_the_two_triggers_each_one_condition_naming_the_pipeline(self):
        self.assertEqual(list(self.block["triggers"]), TRIGGERS)
        for name in TRIGGERS:
            with self.subTest(name):
                self.assertEqual(self.block["triggers"][name], [{"condition": 'glob(BITBUCKET_BRANCH, "**")', "pipelines": [PIPELINE]}])

    def test_the_release_is_read_from_the_comment_on_the_pipelines_line(self):
        named = release_named(self.text)
        self.assertTrue(named == "__IRONBEE_RELEASE__" or NAME.fullmatch(named or ""), named)
        moved = "\n" + self.text                                               # its place in the file does not matter, its line does
        self.assertEqual(release_named(moved), named)
        self.assertIsNone(release_named(self.text.replace("# IronBee's code review, release", "# release")))

    def test_release_json_agrees_with_the_template(self):
        named, image = release_named(self.text), self.step()["image"]["name"]
        if self.release["version"] is None:
            self.assertEqual((self.release["image"], named, image), (None, "__IRONBEE_RELEASE__", "__IRONBEE_IMAGE__"))
        else:
            self.assertEqual((self.release["version"], self.release["image"]), (named, image))


class ReleaseJson(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (ROOT / RELEASE).read_text()
        self.release = json.loads(self.text)

    def test_its_shape(self):
        self.assertEqual(list(self.release), ["version", "image", "template", "triggerApp"])
        self.assertEqual(self.release["template"], TEMPLATE)
        self.assertEqual(self.release["triggerApp"], TRIGGER_APP)

    def test_its_values_placeholders_or_a_releases(self):
        version, image = self.release["version"], self.release["image"]
        if version is None:
            self.assertIsNone(image)
        else:
            self.assertRegex(version, rf"^{NAME.pattern}$")
            self.assertRegex(image, rf"^{DIGEST_IMAGE.pattern}$")

    def test_every_file_it_names_is_in_the_repository(self):
        for path in (self.release["template"], *self.release["triggerApp"]):
            self.assertTrue((ROOT / path).is_file(), path)

    def test_its_form_is_the_one_a_release_writes(self):
        """jq's own, so that a release's stamp changes the two values' lines alone."""
        self.assertEqual(self.text, json.dumps(self.release, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
