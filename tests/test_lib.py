"""What scripts/lib.sh gives the release and no step's test reaches: the error annotation of `fail`, escaped as GitHub
reads a workflow command, so that no text can start a command line of its own."""
from __future__ import annotations

import subprocess
import unittest

from support import SCRIPTS


def run(snippet: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", f'. "$1"; shift; {snippet}', "_", str(SCRIPTS / "lib.sh"), *args], capture_output=True, text=True)


class Fail(unittest.TestCase):
    def test_percent_cr_and_lf_are_escaped(self):
        p = run('fail "$1" "$2"', "2", "100% sure\r\n::warning::injected\nand\rmore")
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stdout, "::error::100%25 sure%0D%0A::warning::injected%0Aand%0Dmore\n")

    def test_a_text_with_nothing_to_escape_is_as_it_was(self):
        p = run('fail "$1" "$2"', "1", "could not read docker.io/ironbeeai/ironbee-code-review-runner:1.0.0")
        self.assertEqual((p.returncode, p.stdout), (1, "::error::could not read docker.io/ironbeeai/ironbee-code-review-runner:1.0.0\n"))


class Notice(unittest.TestCase):
    def test_escaped_as_an_error_is(self):
        p = run('notice "$1"', "50% done\r\n::add-mask::x")
        self.assertEqual((p.returncode, p.stdout), (0, "::notice::50%25 done%0D%0A::add-mask::x\n"))


if __name__ == "__main__":
    unittest.main()
