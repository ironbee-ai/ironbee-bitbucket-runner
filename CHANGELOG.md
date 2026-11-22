# Changelog

What each release changes for you. Read every entry between your block's release and the one you move to
([Versions](README.md#versions)). A release's page on GitHub names its image by digest.

## 1.1.0

- **IronBee's API serves 1.1.0 and later.** A run or a registration of 1.0.0 is refused (`RUNNER_VERSION_UNSUPPORTED`):
  nothing is reviewed, and the head gets a `neutral` that says to move to 1.1.0. Move the block with
  `ironbee runner setup --update`; nothing you set changes. 1.0.0 stopped inside major version 1 and without a dated
  notice.
- **The profiles are renamed** `self-hosted-quick`, `self-hosted-standard` and `self-hosted-deep`, from
  `ironbee-self-hosted-<depth>`. The pipeline's log and the `profile` of the run's report
  ([What reaches IronBee](docs/what-reaches-ironbee.md#complete-post-v1code-review-runsidcomplete)) name the new one.
  No variable or key of the review file is renamed.
- **An account whose code review is turned off in the console is refused** (`CODE_REVIEW_DISABLED`), at the
  registration and at every run: nothing is reviewed, and the `neutral` says to turn it on
  ([Troubleshooting](docs/troubleshooting.md#ironbee-refused-the-run-or-could-not-be-reached)).
- **The reviewer.** An answer the model cut short, at its output limit or, on Claude, at its context window, is no
  longer taken as a finished one: the review keeps the findings it holds and is posted as partial. With
  `IRONBEE_MODEL_PROVIDER` set to `openai`, a broken or unfinished stream is sent again as a failed attempt, a tool
  call with malformed arguments is answered as not run, and a retry waits at least the server's `retry-after`.

## 1.0.0

The first release.
