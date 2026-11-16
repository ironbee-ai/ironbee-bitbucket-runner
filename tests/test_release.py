"""The release (scripts/release.sh), step by step, in a repository of its own whose origin is a local one: the inputs and
the names they give, the plan over the tags, the digest against a stub registry (tests/stubs/docker) by its own step and
again by the publish, the stamp of the
real template and release.json (a second release over the first one's values among them), the commit, the tags and the
push, and the GitHub release against the stub GitHub. No network."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest

from support import IMAGE, RELEASE, REPO, ROOT, TEMPLATE, TRIGGER_APP, ScriptTest

DIGEST = "sha256:" + "a" * 64                                # the image the release names
OTHER = "sha256:" + "b" * 64                                 # another image
BOT = "github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>"
GIT = {"GIT_AUTHOR_NAME": "dev", "GIT_AUTHOR_EMAIL": "dev@example.com", "GIT_COMMITTER_NAME": "dev", "GIT_COMMITTER_EMAIL": "dev@example.com",
       "GIT_CONFIG_NOSYSTEM": "1"}
NAME_LINE = re.compile(r"^(\s*ironbee-code-review:\s+# IronBee's code review, release )(\S+)$", re.M)
IMAGE_LINE = re.compile(r"^(\s*name:\s+)(__IRONBEE_IMAGE__|docker\.io/\S+)$", re.M)


def stamped(text: str, digest: str, name: str) -> str:
    """The template as a release stamps it."""
    return IMAGE_LINE.sub(rf"\g<1>{IMAGE}@{digest}", NAME_LINE.sub(rf"\g<1>{name}", text))


def stamped_json(text: str, digest: str, name: str) -> str:
    return json.dumps({**json.loads(text), "version": name, "image": f"{IMAGE}@{digest}"}, indent=2) + "\n"


def unreleased(text: str) -> str:
    """The template as it is before the first release: its two placeholders."""
    return IMAGE_LINE.sub(r"\g<1>__IRONBEE_IMAGE__", NAME_LINE.sub(r"\g<1>__IRONBEE_RELEASE__", text))


def unreleased_json(text: str) -> str:
    return json.dumps({**json.loads(text), "version": None, "image": None}, indent=2) + "\n"


class Release(ScriptTest):
    """Each test's repository starts from main's files as they are: a release's values once main is released, the
    placeholders before. A test that needs the form before the first release puts it back (`unreleased`)."""

    def setUp(self) -> None:
        super().setUp()
        self.origin, self.work = self.tmp / "origin.git", self.tmp / "work"
        self.git("init", "--quiet", "--bare", "--initial-branch=main", str(self.origin), cwd=self.tmp)
        self.git("init", "--quiet", "--initial-branch=main", str(self.work), cwd=self.tmp)
        for path in (TEMPLATE, RELEASE, *TRIGGER_APP):
            (self.work / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / path, self.work / path)
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "the block and the trigger app")
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "--quiet", "origin", "main")
        self.registry = {"tags": {f"{IMAGE}:1.0.0-rc.2": DIGEST, f"{IMAGE}:1.0.0": DIGEST}}

    def unreleased(self) -> tuple:
        """The working copy's template and release.json put back to their form before the first release, uncommitted."""
        for path, put_back in ((TEMPLATE, unreleased), (RELEASE, unreleased_json)):
            (self.work / path).write_text(put_back((self.work / path).read_text()))
        template, release = (self.work / TEMPLATE).read_text(), (self.work / RELEASE).read_text()
        self.assertEqual((template.count("__IRONBEE_IMAGE__"), template.count("__IRONBEE_RELEASE__")), (1, 1))
        return template, release

    def git(self, *args, cwd=None) -> str:
        env = {"PATH": os.environ["PATH"], "HOME": str(self.tmp), **GIT}
        return subprocess.run(["git", *args], cwd=cwd or self.work, env=env, capture_output=True, text=True, check=True).stdout.strip()

    def ref(self, name: str, where=None) -> str:
        """The commit a ref names in the origin (or in `where`), or "" when there is no such ref."""
        p = subprocess.run(["git", "rev-parse", "-q", "--verify", f"{name}^{{commit}}"], cwd=where or self.origin, capture_output=True, text=True)
        return p.stdout.strip()

    def refs(self) -> str:
        return self.git("for-each-ref", "--format=%(refname) %(objectname)", cwd=self.origin)

    def tag(self, tag: str, digest: str = DIGEST, name: str | None = None) -> None:
        """A tag as a release writes it: a commit on main naming `digest` and `name` (the tag's own when not given), tagged
        and pushed."""
        name = name or tag[1:]
        for path, stamp in ((TEMPLATE, stamped), (RELEASE, stamped_json)):
            (self.work / path).write_text(stamp((self.work / path).read_text(), digest, name))
        self.git("commit", "--quiet", "--allow-empty", "-am", f"chore(release): {tag}")
        self.git("tag", "-a", tag, "-m", tag)
        self.git("push", "--quiet", "origin", "main", f"refs/tags/{tag}")

    def release(self, step: str, version: str = "1.0.0", rc: str = "2", digest: str = DIGEST, **env):
        """A step as the workflow runs it, with its three inputs."""
        files = {k: self.tmp / k for k in ("docker.json", "docker.calls")}
        files["docker.json"].write_text(json.dumps(self.registry)); files["docker.calls"].write_text("")
        e = {"IRONBEE_VERSION": version, "IRONBEE_RC": rc, "IRONBEE_IMAGE_DIGEST": digest, "GITHUB_REF": "refs/heads/main",
             "GIT_CONFIG_NOSYSTEM": "1", "STUB_DOCKER_STATE": str(files["docker.json"]), "STUB_DOCKER_CALLS": str(files["docker.calls"]), **env}
        ran = self.run_script("release.sh", e, args=(step,), cwd=self.work)
        self.docker = [json.loads(line) for line in files["docker.calls"].read_text().splitlines()]
        return ran

    def at(self, ref: str, path: str) -> str:
        return self.git("show", f"{ref}:{path}", cwd=self.origin)


STEPS = ("plan", "digest", "stamp", "publish", "github-release")


class Inputs(Release):
    def test_the_version_by_its_form(self):
        for version in ("", "1.0", "v1.0.0", "01.0.0", "1.00.0", "1.0.0-rc.1", "1.0.0 ", "1.0.0\n", "latest", "1.0.0;id", "$(id)"):
            with self.subTest(version=version):
                ran = self.release("digest", version=version)
                self.assertEqual(ran.code, 2, ran.out)
                self.assertTrue(ran.out.startswith("::error::version is not MAJOR.MINOR.PATCH"), ran.out)
                self.assertEqual(self.docker, [])

    def test_the_rc_by_its_form(self):
        for rc in ("0", "01", "rc.1", "-1", "1.2", "1 ", "1\n", "x", "$(id)"):
            with self.subTest(rc=rc):
                ran = self.release("digest", rc=rc)
                self.assertEqual(ran.code, 2, ran.out)
                self.assertIn("::error::rc is neither empty (a release) nor a whole number from 1 (a pre-release)", ran.out)
                self.assertEqual(self.docker, [])

    def test_every_step_checks_its_inputs_first(self):
        for step in STEPS:
            with self.subTest(step):
                ran = self.release(step, version="1.0")
                self.assertEqual(ran.code, 2, ran.out)
                self.assertIn("version is not MAJOR.MINOR.PATCH", ran.out)
                self.assertEqual((self.docker, ran.calls), ([], []))

    def test_the_digest_by_its_form(self):
        for digest in ("", "a" * 64, "sha256:" + "A" * 64, "sha256:" + "a" * 63, "sha256:" + "a" * 65, "sha512:" + "a" * 64, "sha256:" + "0" * 64):
            for step in STEPS:
                with self.subTest(digest=digest, step=step):
                    ran = self.release(step, digest=digest)
                    self.assertEqual(ran.code, 2, ran.out)
                    self.assertIn("::error::IRONBEE_IMAGE_DIGEST is ", ran.out)
                    self.assertEqual((self.docker, ran.calls), ([], []))

    def test_what_comes_from_the_inputs(self):
        names = {("1.2.3", "4"): f"tag v1.2.3-rc.4, release 1.2.3-rc.4 (a pre-release), image {IMAGE}@{DIGEST}, floating tag v0",
                 ("0.3.0", "1"): f"tag v0.3.0-rc.1, release 0.3.0-rc.1 (a pre-release), image {IMAGE}@{DIGEST}, floating tag v0",
                 ("1.2.3", "12"): f"tag v1.2.3-rc.12, release 1.2.3-rc.12 (a pre-release), image {IMAGE}@{DIGEST}, floating tag v0",
                 ("1.2.3", ""): f"tag v1.2.3, release 1.2.3, image {IMAGE}@{DIGEST}, floating tag v1 and v0",
                 ("12.0.10", ""): f"tag v12.0.10, release 12.0.10, image {IMAGE}@{DIGEST}, floating tag v12 and v0"}
        for (version, rc), line in names.items():
            with self.subTest(version=version, rc=rc):
                ran = self.release("plan", version=version, rc=rc)
                self.assertEqual(ran.code, 0, ran.out)
                self.assertIn(line, ran.out.splitlines())                                       # the whole line: nothing after it

    def test_major_version_0_is_never_released(self):
        ran = self.release("plan", version="0.9.0", rc="")
        self.assertEqual(ran.code, 2)
        self.assertIn("v0 is the tag of the newest release or pre-release", ran.out)

    def test_the_steps(self):
        for args in ((), ("nope",), ("plan", "x")):
            with self.subTest(args):
                ran = self.run_script("release.sh", {"IRONBEE_VERSION": "1.0.0", "IRONBEE_RC": "", "IRONBEE_IMAGE_DIGEST": DIGEST}, args=args, cwd=self.work)
                self.assertEqual(ran.code, 2)
                self.assertIn("usage: release.sh plan|digest|stamp|publish|github-release", ran.out)


class Plan(Release):
    def test_a_new_pre_release(self):
        ran = self.release("plan")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertIn("v1.0.0-rc.2 is new", ran.out)
        self.assertNotIn("::notice::", ran.out)
        self.assertEqual(self.docker, [])                                                     # the registry is the digest step's

    def test_from_main_alone(self):
        ran = self.release("plan", GITHUB_REF="refs/heads/feat/something")
        self.assertEqual(ran.code, 2)
        self.assertIn("a release runs from main", ran.out)

    def test_a_tag_that_names_another_image_or_release_is_never_moved(self):
        for digest, name in ((OTHER, "1.0.0-rc.2"), (DIGEST, "1.0.0-rc.1")):
            with self.subTest(digest=digest, name=name):
                self.setUp()
                self.tag("v1.0.0-rc.2", digest, name)
                ran = self.release("plan")
                self.assertEqual(ran.code, 1, ran.out)
                self.assertIn("v1.0.0-rc.2 exists and names", ran.out)
                self.assertIn("a tag is never moved", ran.out)

    def test_a_tag_whose_template_and_release_json_disagree_is_never_moved(self):
        self.tag("v1.0.0-rc.2")
        path = self.work / TEMPLATE
        path.write_text(stamped(path.read_text(), OTHER, "1.0.0-rc.2"))
        self.git("commit", "--quiet", "-am", "the template alone moved"); self.git("tag", "-f", "-a", "v1.0.0-rc.2", "-m", "moved")
        self.git("push", "--quiet", "--force", "origin", "main", "refs/tags/v1.0.0-rc.2")
        ran = self.release("plan")
        self.assertEqual(ran.code, 1, ran.out)
        self.assertIn("a tag is never moved", ran.out)

    def test_a_run_again_after_its_push(self):
        self.tag("v1.0.0-rc.2")
        ran = self.release("plan")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertIn("::notice::v1.0.0-rc.2 is already pushed with this image and name: this run moves nothing", ran.out)

    def test_a_release_is_never_below_the_newest_one(self):
        self.tag("v1.9.0"); self.tag("v1.10.0")                  # by number, not by text
        ran = self.release("plan", version="1.9.5", rc="")
        self.assertEqual(ran.code, 1, ran.out)
        self.assertIn("v1.9.5 is below the newest release, v1.10.0", ran.out)
        ran = self.release("plan", version="1.10.1", rc="")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertIn("v1.10.1 is new; the newest release is v1.10.0", ran.out)
        self.assertEqual(self.release("plan", version="1.9.5", rc="1").code, 0)   # a pre-release is not held to it

    def test_a_released_version_takes_no_more_pre_releases(self):
        self.tag("v1.0.0")
        ran = self.release("plan", rc="3")
        self.assertEqual(ran.code, 1)
        self.assertIn("v1.0.0 is released: it takes no more pre-releases", ran.out)

    def test_a_template_the_release_could_not_stamp(self):
        """In the form main holds and in the form before the first release: the step image's line is found by its form."""
        for form, text in (("main's", (self.work / TEMPLATE).read_text()), ("unreleased", unreleased((self.work / TEMPLATE).read_text()))):
            [line] = [l for l in text.splitlines() if IMAGE_LINE.fullmatch(l)]
            value = IMAGE_LINE.fullmatch(line).group(2)
            variants = {"no release comment": (text.replace("# IronBee's code review, release", "# release"), "the pipeline's line naming the release is there 0 times"),
                        "the image line twice": (text.replace(line + "\n", (line + "\n") * 2), "the step image's name line is there 2 times"),
                        "another image": (text.replace(line, line.replace(value, "docker.io/acme/other:latest")), "the step image's name line is there 0 times"),
                        "a short digest": (text.replace(line, line.replace(value, f"{IMAGE}@sha256:{'a' * 63}")), "the step image's name line is there 0 times")}
            for label, (variant, says) in variants.items():
                with self.subTest(form=form, variant=label):
                    self.assertNotEqual(variant, text)
                    (self.work / TEMPLATE).write_text(variant)
                    ran = self.release("plan")
                    self.assertEqual(ran.code, 2, ran.out)
                    self.assertIn(f"{TEMPLATE}: {says}", ran.out)

    def test_a_release_json_of_another_shape(self):
        good = json.loads((self.work / RELEASE).read_text())
        for label, data in {"a member more": {**good, "extra": 1}, "a member less": {k: v for k, v in good.items() if k != "image"},
                            "another template": {**good, "template": "bitbucket-pipelines.yml"}, "the app's files reordered": {**good, "triggerApp": good["triggerApp"][::-1]},
                            "a version of another type": {**good, "version": 1}, "a list": [good]}.items():
            with self.subTest(label):
                (self.work / RELEASE).write_text(json.dumps(data))
                ran = self.release("plan")
                self.assertEqual(ran.code, 2, ran.out)
                self.assertIn(f"{RELEASE} is not release.json's shape", ran.out)
        (self.work / RELEASE).write_text("{not json")
        self.assertEqual(self.release("plan").code, 2)

    def test_a_trigger_app_file_missing(self):
        (self.work / "trigger-app" / "package-lock.json").unlink()
        ran = self.release("plan")
        self.assertEqual(ran.code, 2)
        self.assertIn("trigger-app/package-lock.json is listed in release.json and missing", ran.out)


class Digest(Release):
    def test_the_tag_of_the_releases_name_names_the_digest_given(self):
        for version, rc, name in (("1.0.0", "2", "1.0.0-rc.2"), ("1.0.0", "", "1.0.0")):
            with self.subTest(name=name):
                ran = self.release("digest", version=version, rc=rc)
                self.assertEqual(ran.code, 0, ran.out)
                self.assertEqual(self.docker, [["buildx", "imagetools", "inspect", f"{IMAGE}:{name}", "--format", "{{json .Manifest}}"]])
                self.assertIn(f"{IMAGE}:{name} is {IMAGE}@{DIGEST} on Docker Hub, the digest given", ran.out)

    def test_a_digest_docker_hub_does_not_hold_under_that_name_is_refused(self):
        ran = self.release("digest", digest=OTHER)
        self.assertEqual(ran.code, 1, ran.out)
        self.assertIn(f"{IMAGE}:1.0.0-rc.2 is {IMAGE}@{DIGEST} on Docker Hub, not the digest given, {OTHER}", ran.out)
        self.registry["tags"][f"{IMAGE}:1.0.0"] = OTHER                                       # a tag moved to another image
        ran = self.release("digest", rc="")
        self.assertEqual(ran.code, 1, ran.out)

    def test_a_name_not_in_the_registry(self):
        ran = self.release("digest", rc="9")
        self.assertEqual(ran.code, 1)
        self.assertIn(f"could not read {IMAGE}:1.0.0-rc.9", ran.out)


class Stamp(Release):
    def changed_lines(self, path: str, before: str) -> list:
        after = (self.work / path).read_text().splitlines()
        self.assertEqual(len(after), len(before.splitlines()))
        return [(a, b) for a, b in zip(before.splitlines(), after) if a != b]

    def test_the_placeholders_become_the_image_and_the_name_and_nothing_else(self):
        template, release = self.unreleased()
        ran = self.release("stamp")
        self.assertEqual(ran.code, 0, ran.out)
        changed = self.changed_lines(TEMPLATE, template)
        self.assertEqual([b.strip() for _, b in changed], ["ironbee-code-review:                          # IronBee's code review, release 1.0.0-rc.2",
                                                            f"name: {IMAGE}@{DIGEST}"])
        self.assertEqual(json.loads((self.work / RELEASE).read_text()), {**json.loads(release), "version": "1.0.0-rc.2", "image": f"{IMAGE}@{DIGEST}"})
        self.assertEqual(len(self.changed_lines(RELEASE, release)), 2)                        # the file keeps its form
        self.assertIn(f"stamped {TEMPLATE} and {RELEASE}: {IMAGE}@{DIGEST} (was none), release 1.0.0-rc.2 (was none)", ran.out)

    def test_main_as_it_is_takes_a_release_over_whatever_it_holds(self):
        """main's own files: a release's values once main is released, the placeholders before."""
        template, release = (self.work / TEMPLATE).read_text(), (self.work / RELEASE).read_text()
        held = json.loads(release)
        ran = self.release("stamp", rc="9", digest=OTHER)
        self.assertEqual(ran.code, 0, ran.out)
        self.assertEqual([b.strip() for _, b in self.changed_lines(TEMPLATE, template)],
                         ["ironbee-code-review:                          # IronBee's code review, release 1.0.0-rc.9", f"name: {IMAGE}@{OTHER}"])
        self.assertEqual(json.loads((self.work / RELEASE).read_text()), {**held, "version": "1.0.0-rc.9", "image": f"{IMAGE}@{OTHER}"})
        self.assertEqual(len(self.changed_lines(RELEASE, release)), 2)
        self.assertIn(f"(was {held['image'] or 'none'}), release 1.0.0-rc.9 (was {held['version'] or 'none'})", ran.out)

    def test_a_second_release_over_the_first_ones_values(self):
        self.assertEqual(self.release("stamp").code, 0)
        template, release = (self.work / TEMPLATE).read_text(), (self.work / RELEASE).read_text()
        ran = self.release("stamp", rc="", digest=OTHER)
        self.assertEqual(ran.code, 0, ran.out)
        changed = self.changed_lines(TEMPLATE, template)
        self.assertEqual([b.strip() for _, b in changed], ["ironbee-code-review:                          # IronBee's code review, release 1.0.0",
                                                            f"name: {IMAGE}@{OTHER}"])
        self.assertEqual(json.loads((self.work / RELEASE).read_text())["version"], "1.0.0")
        self.assertEqual(json.loads((self.work / RELEASE).read_text())["image"], f"{IMAGE}@{OTHER}")
        self.assertEqual(len(self.changed_lines(RELEASE, release)), 2)
        self.assertIn(f"(was {IMAGE}@{DIGEST}), release 1.0.0 (was 1.0.0-rc.2)", ran.out)

    def test_twice_is_once(self):
        self.release("stamp")
        once = ((self.work / TEMPLATE).read_text(), (self.work / RELEASE).read_text())
        self.assertEqual(self.release("stamp").code, 0)
        self.assertEqual(((self.work / TEMPLATE).read_text(), (self.work / RELEASE).read_text()), once)

    def test_a_file_it_cannot_stamp_is_left_as_it_is(self):
        text = (self.work / TEMPLATE).read_text().replace("# IronBee's code review, release", "# release")
        (self.work / TEMPLATE).write_text(text)
        release = (self.work / RELEASE).read_text()
        ran = self.release("stamp")
        self.assertEqual(ran.code, 2, ran.out)
        self.assertEqual(((self.work / TEMPLATE).read_text(), (self.work / RELEASE).read_text()), (text, release))


class Publish(Release):
    def test_a_pre_release(self):
        base = self.ref("main")
        ran = self.release("publish")
        self.assertEqual(ran.code, 0, ran.out)
        head = self.ref("main")
        self.assertEqual(self.git("rev-parse", f"{head}~1", cwd=self.origin), base)
        self.assertEqual(self.git("log", "-1", "--format=%s|%an <%ae>|%cn <%ce>", head, cwd=self.origin), f"chore(release): v1.0.0-rc.2|{BOT}|{BOT}")
        self.assertEqual((self.ref("refs/tags/v1.0.0-rc.2"), self.ref("refs/tags/v0"), self.ref("refs/tags/v1")), (head, head, ""))
        self.assertIn("tagged v1.0.0-rc.2; v0 moved to it", ran.out)
        for tag, message in (("v1.0.0-rc.2", "1.0.0-rc.2: a pre-release for IronBee's own tests"), ("v0", "v0: the newest release or pre-release (v1.0.0-rc.2)")):
            self.assertEqual(self.git("cat-file", "-t", f"refs/tags/{tag}", cwd=self.origin), "tag")     # annotated
            self.assertEqual(self.git("tag", "-l", "--format=%(taggername) %(taggeremail)|%(contents:subject)", tag, cwd=self.origin), f"{BOT}|{message}")
        self.assertEqual(json.loads(self.at("v1.0.0-rc.2", RELEASE))["version"], "1.0.0-rc.2")
        self.assertIn("# IronBee's code review, release 1.0.0-rc.2\n", self.at("v1.0.0-rc.2", TEMPLATE) + "\n")
        self.assertEqual(sorted(self.git("diff", "--name-only", base, head, cwd=self.origin).splitlines()), sorted([RELEASE, TEMPLATE]))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_a_release_moves_its_major_versions_tag_and_v0(self):
        self.tag("v1.0.0-rc.1"); self.git("tag", "-a", "v0", "-m", "v0"); self.git("push", "--quiet", "origin", "v0")
        ran = self.release("publish", rc="")
        self.assertEqual(ran.code, 0, ran.out)
        head = self.ref("main")
        self.assertEqual((self.ref("refs/tags/v1.0.0"), self.ref("refs/tags/v1"), self.ref("refs/tags/v0")), (head, head, head))
        self.assertEqual(self.git("tag", "-l", "--format=%(contents:subject)", "v1", cwd=self.origin), "v1: the newest release of major version 1 (v1.0.0)")
        self.assertEqual(self.git("tag", "-l", "--format=%(contents:subject)", "v1.0.0", cwd=self.origin), "1.0.0: a release")
        self.assertIn("tagged v1.0.0; v1 and v0 moved to it", ran.out)

    def test_each_tag_holds_its_own_releases_values(self):
        """A pre-release, a later one with another image, then the release: each tag's files name that release alone."""
        self.registry["tags"].update({f"{IMAGE}:1.0.0-rc.3": OTHER, f"{IMAGE}:1.0.0": OTHER})
        self.assertEqual(self.release("publish").code, 0)
        self.assertEqual(self.release("publish", rc="3", digest=OTHER).code, 0)
        self.assertEqual(self.release("publish", rc="", digest=OTHER).code, 0)
        for tag, digest, name in (("v1.0.0-rc.2", DIGEST, "1.0.0-rc.2"), ("v1.0.0-rc.3", OTHER, "1.0.0-rc.3"), ("v1.0.0", OTHER, "1.0.0")):
            with self.subTest(tag):
                data = json.loads(self.at(tag, RELEASE))
                self.assertEqual((data["version"], data["image"]), (name, f"{IMAGE}@{digest}"))
                template = self.at(tag, TEMPLATE)
                self.assertIn(f"# IronBee's code review, release {name}\n", template + "\n")
                self.assertIn(f"name: {IMAGE}@{digest}\n", template)
                self.assertNotIn("__IRONBEE_", template)
        self.assertEqual(self.ref("refs/tags/v0"), self.ref("refs/tags/v1.0.0"))

    def v0_at(self, name: str) -> None:
        self.git("tag", "-f", "-a", "v0", "-m", "v0", f"refs/tags/{name}^{{commit}}"); self.git("push", "--quiet", "--force", "origin", "refs/tags/v0")

    def test_v0_never_goes_back_to_an_older_line(self):
        self.tag("v2.0.0-rc.1"); self.v0_at("v2.0.0-rc.1")
        ahead = self.ref("refs/tags/v0")
        ran = self.release("plan", rc="")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertIn("floating tag v1; v0 stays, v2.0.0-rc.1 being later", ran.out)
        ran = self.release("publish", rc="")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertEqual((self.ref("refs/tags/v1"), self.ref("refs/tags/v0")), (self.ref("main"), ahead))
        self.assertIn("tagged v1.0.0; v1 moved to it", ran.out); self.assertIn("v0 stays, v2.0.0-rc.1 being later", ran.out)

    def test_a_pre_release_of_an_older_line_moves_no_floating_tag(self):
        self.tag("v2.0.0-rc.1"); self.v0_at("v2.0.0-rc.1")
        ahead = self.ref("refs/tags/v0")
        self.registry["tags"][f"{IMAGE}:1.0.0-rc.3"] = DIGEST
        ran = self.release("publish", rc="3")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertEqual(self.ref("refs/tags/v0"), ahead)
        self.assertIn("tagged v1.0.0-rc.3; v0 stays, v2.0.0-rc.1 being later", ran.out)

    def test_a_release_whose_v0_moved_during_the_run_pushes_nothing(self):
        self.tag("v1.0.0-rc.1"); self.git("tag", "-a", "v0", "-m", "v0"); self.git("push", "--quiet", "origin", "v0")
        main = self.ref("main")
        hook = self.work / ".git" / "hooks" / "pre-push"                                                     # moves origin's v0 after the tags were read
        hook.write_text(f"#!/bin/sh\ngit -C '{self.origin}' tag -f -a v0 -m elsewhere v1.0.0-rc.1 > /dev/null\n"); hook.chmod(0o755)
        ran = self.release("publish", rc="")
        self.assertEqual(ran.code, 1, ran.out)
        self.assertIn("nothing was pushed", ran.out)
        self.assertEqual((self.ref("main"), self.git("tag", "-l", "v1.0.0", cwd=self.origin)), (main, ""))

    def test_a_kept_v0_moved_during_the_run_and_nothing_is_pushed(self):
        self.tag("v2.0.0-rc.1"); self.v0_at("v2.0.0-rc.1")
        main = self.ref("main")
        hook = self.work / ".git" / "hooks" / "post-commit"                                              # after the tags were read, before the push
        hook.write_text(f"#!/bin/sh\ngit -C '{self.origin}' tag -f -a v0 -m elsewhere main~1 > /dev/null\n"); hook.chmod(0o755)
        ran = self.release("publish", rc="")
        self.assertEqual(ran.code, 1, ran.out)
        self.assertIn("nothing was pushed", ran.out)
        self.assertEqual((self.ref("main"), self.git("tag", "-l", "v1.0.0", cwd=self.origin)), (main, ""))

    def test_v0_moves_from_a_pre_release_to_its_release_and_on(self):
        self.tag("v1.0.0-rc.2"); self.v0_at("v1.0.0-rc.2")
        self.assertEqual(self.release("publish", rc="").code, 0)                                         # a release follows its pre-release
        self.assertEqual(self.ref("refs/tags/v0"), self.ref("refs/tags/v1.0.0"))
        self.registry["tags"][f"{IMAGE}:1.0.1-rc.1"] = OTHER
        self.assertEqual(self.release("publish", version="1.0.1", rc="1", digest=OTHER).code, 0)        # and a later pre-release follows it
        self.assertEqual(self.ref("refs/tags/v0"), self.ref("refs/tags/v1.0.1-rc.1"))
        self.assertEqual(self.ref("refs/tags/v1"), self.ref("refs/tags/v1.0.0"))                         # v1 follows the releases alone

    def test_a_digest_docker_hub_does_not_hold_is_never_stamped(self):
        """Run by hand, the steps may skip the digest step: the publish checks the digest again before it stamps."""
        before = self.refs()
        ran = self.release("publish", digest=OTHER)
        self.assertEqual(ran.code, 1, ran.out)
        self.assertIn(f"{IMAGE}:1.0.0-rc.2 is {IMAGE}@{DIGEST} on Docker Hub, not the digest given, {OTHER}", ran.out)
        self.assertEqual(self.docker, [["buildx", "imagetools", "inspect", f"{IMAGE}:1.0.0-rc.2", "--format", "{{json .Manifest}}"]])
        self.assertEqual(self.refs(), before)
        self.assertEqual(self.git("status", "--porcelain"), "")                                         # nothing stamped
        self.registry["tags"] = {}
        ran = self.release("publish")
        self.assertEqual(ran.code, 1, ran.out)
        self.assertIn(f"could not read {IMAGE}:1.0.0-rc.2", ran.out)
        self.assertEqual(self.refs(), before)

    def test_each_floating_tag_says_where_it_moved_from(self):
        self.tag("v1.0.0-rc.1"); self.v0_at("v1.0.0-rc.1")
        v0 = self.git("rev-parse", "--short", "refs/tags/v0^{commit}", cwd=self.origin)
        ran = self.release("publish", rc="")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertIn(f"tagged v1.0.0; v1 and v0 moved to it (v1 from new, v0 from {v0})", ran.out)

    def test_a_stale_local_floating_tag_is_read_again(self):
        self.assertEqual(self.release("publish").code, 0)                                                # origin's v0 at rc.2
        self.git("tag", "-f", "-a", "v0", "-m", "stale", "main~1")                                      # this clone's, behind
        ran = self.release("publish", rc="")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertEqual(self.ref("refs/tags/v0"), self.ref("refs/tags/v1.0.0"))

    def test_a_tag_a_refused_run_left_is_dropped_and_the_run_again_publishes(self):
        self.git("tag", "-a", "v1.0.0-rc.2", "-m", "left by a refused run")                              # never pushed
        self.git("tag", "mine")                                                                         # someone's own, kept
        ran = self.release("publish")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertNotIn("already pushed", ran.out)
        self.assertEqual(self.ref("refs/tags/v1.0.0-rc.2"), self.ref("main"))
        self.assertEqual(self.git("tag", "-l", "mine"), "mine")

    def test_main_already_naming_the_release_is_an_empty_commit(self):
        self.assertEqual(self.release("stamp", rc="").code, 0)
        self.git("commit", "--quiet", "-am", "stamped by hand"); self.git("push", "--quiet", "origin", "main")
        ran = self.release("publish", rc="")
        self.assertEqual(ran.code, 0, ran.out)
        head = self.ref("main")
        self.assertEqual(self.git("diff", "--name-only", f"{head}~1", head, cwd=self.origin), "")
        self.assertEqual(self.ref("refs/tags/v1.0.0"), head)

    def test_a_run_again_after_its_push_moves_nothing(self):
        self.registry["tags"][f"{IMAGE}:1.0.0-rc.3"] = OTHER
        self.assertEqual(self.release("publish").code, 0)
        self.assertEqual(self.release("publish", rc="3", digest=OTHER).code, 0)   # v0 moves on to rc.3
        before = self.refs()
        self.registry["tags"] = {}                                                 # nothing is stamped, so nothing is read there
        ran = self.release("publish")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertIn("::notice::v1.0.0-rc.2 is already pushed with this image and name: nothing is moved", ran.out)
        self.assertEqual((self.refs(), self.docker), (before, []))
        self.assertEqual(self.ref("refs/tags/v0"), self.ref("refs/tags/v1.0.0-rc.3"))

    def test_a_plan_of_a_pushed_tag_claims_no_floating_tag(self):
        self.assertEqual(self.release("publish").code, 0)
        ran = self.release("plan")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertIn("tag v1.0.0-rc.2, release 1.0.0-rc.2 (a pre-release)", ran.out); self.assertNotIn("floating tag", ran.out)

    def test_a_tag_that_names_another_release(self):
        self.tag("v1.0.0-rc.2", OTHER)
        before = self.refs()
        ran = self.release("publish")
        self.assertEqual(ran.code, 1)
        self.assertIn("a tag is never moved", ran.out)
        self.assertEqual(self.refs(), before)

    def test_main_moved_meanwhile_and_nothing_is_pushed(self):
        other = self.tmp / "other"
        self.git("clone", "--quiet", str(self.origin), str(other), cwd=self.tmp)
        (other / "README.md").write_text("x\n"); self.git("add", ".", cwd=other); self.git("commit", "--quiet", "-m", "x", cwd=other)
        self.git("push", "--quiet", "origin", "main", cwd=other)
        before = self.refs()
        ran = self.release("publish")
        self.assertEqual(ran.code, 1, ran.out)
        self.assertIn("nothing was pushed", ran.out)
        self.assertEqual(self.refs(), before)

    def test_the_newest_release_puts_a_hand_moved_v0_back(self):
        self.tag("v1.0.0-rc.1"); self.git("tag", "-a", "v0", "-m", "v0"); self.git("push", "--quiet", "origin", "v0")
        self.git("tag", "-f", "-a", "v0", "-m", "by hand", "main~1", cwd=self.origin)
        ran = self.release("publish")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertEqual(self.ref("refs/tags/v0"), self.ref("refs/tags/v1.0.0-rc.2"))

    def test_an_older_lines_release_with_no_v0_anywhere(self):
        self.tag("v2.0.0-rc.1")                                                                          # tagged before v0 existed
        ran = self.release("publish", rc="")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertEqual((self.ref("refs/tags/v0"), self.ref("refs/tags/v1")), ("", self.ref("refs/tags/v1.0.0")))
        self.assertIn("no v0 is made, v2.0.0-rc.1 being later", ran.out)

    def test_a_working_tree_with_changes(self):
        (self.work / TEMPLATE).write_text((self.work / TEMPLATE).read_text() + "# more\n")
        before = self.refs()
        ran = self.release("publish")
        self.assertEqual(ran.code, 2)
        self.assertIn("the working tree holds changes", ran.out)
        self.assertEqual(self.refs(), before)


class GithubRelease(Release):
    def made(self, ran, tag: str) -> dict:
        self.assertEqual(ran.code, 0, ran.out)
        self.assertEqual([c["method"] for c in ran.writes()], ["POST"])
        self.assertIn(f"made the GitHub release {tag}", ran.out)
        return ran.state["releases"][tag]

    def test_a_pre_release(self):
        self.tag("v1.0.0-rc.2")
        made = self.made(self.release("github-release"), "v1.0.0-rc.2")
        self.assertEqual({k: made[k] for k in ("tag_name", "name", "prerelease", "make_latest")},
                         {"tag_name": "v1.0.0-rc.2", "name": "v1.0.0-rc.2", "prerelease": True, "make_latest": "false"})
        self.assertEqual(made["body"], f"A pre-release of 1.0.0 for IronBee's own tests, not for production.\n\nImage: `{IMAGE}@{DIGEST}`\n\n"
                                       f"The block: `{TEMPLATE}` at `v1.0.0-rc.2`. The trigger app's source: `trigger-app/` at `v1.0.0-rc.2`.\n\n"
                                       "`ironbee runner setup --host bitbucket --version 1.0.0-rc.2` sets this release up.\n\n")

    def test_a_release(self):
        self.tag("v1.0.0")
        made = self.made(self.release("github-release", rc=""), "v1.0.0")
        self.assertEqual((made["prerelease"], made["make_latest"]), (False, "true"))
        self.assertTrue(made["body"].startswith(f"Image: `{IMAGE}@{DIGEST}`"))

    def test_a_release_that_exists_is_left_as_it_is(self):
        self.tag("v1.0.0-rc.2")
        self.state["releases"] = {"v1.0.0-rc.2": {"tag_name": "v1.0.0-rc.2", "id": 1}}
        ran = self.release("github-release")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertIn("::notice::the GitHub release v1.0.0-rc.2 exists: nothing to do", ran.out)
        self.assertEqual(ran.writes(), [])

    def test_a_tag_not_pushed(self):
        ran = self.release("github-release")
        self.assertEqual(ran.code, 1)
        self.assertIn("v1.0.0-rc.2 is not pushed", ran.out)
        self.assertEqual(ran.calls, [])

    def test_a_repository_by_its_form(self):
        self.tag("v1.0.0-rc.2")
        for repo in ("", "acme", "a/b/c", "/x", "a b/c"):
            with self.subTest(repo=repo):
                ran = self.release("github-release", GITHUB_REPOSITORY=repo)
                self.assertEqual(ran.code, 2)
                self.assertEqual(ran.calls, [])

    def test_a_create_that_fails(self):
        self.tag("v1.0.0-rc.2")
        self.state["fail"] = [{"method": "POST", "path": f"repos/{REPO}/releases", "status": 502, "times": 3}]
        ran = self.release("github-release")
        self.assertEqual(ran.code, 1)
        self.assertIn("GitHub did not make the release v1.0.0-rc.2 (HTTP 502)", ran.out)
        self.assertEqual([c["method"] for c in ran.calls], ["GET", "POST", "GET"])     # a POST is not sent again on a 5xx
        self.assertEqual(ran.sleeps, [])

    def test_a_create_made_without_an_answer_is_found(self):
        self.tag("v1.0.0-rc.2")
        self.state["fail"] = [{"method": "POST", "path": f"repos/{REPO}/releases", "status": 502, "times": 1, "made": True}]
        ran = self.release("github-release")
        self.assertEqual(ran.code, 0, ran.out)
        self.assertEqual(list(ran.state["releases"]), ["v1.0.0-rc.2"])
        self.assertEqual([c["method"] for c in ran.calls], ["GET", "POST", "GET"])

    def test_a_read_that_fails_is_tried_three_times(self):
        self.tag("v1.0.0-rc.2")
        self.state["fail"] = [{"method": "GET", "path": f"repos/{REPO}/releases/tags", "status": 503, "times": 3}]
        ran = self.release("github-release")
        self.assertEqual(ran.code, 1)
        self.assertIn("GitHub did not say whether the release v1.0.0-rc.2 exists (HTTP 503)", ran.out)
        self.assertEqual(ran.sleeps, ["2", "5"])


if __name__ == "__main__":
    unittest.main()
