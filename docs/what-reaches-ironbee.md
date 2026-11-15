# What reaches IronBee

Your code is read in your own step, and your model is called from it. A run calls IronBee at most twice, when it
starts and when it ends; registering a repository is one more call, and the setup's probe reads one page of IronBee's
list of runs. Each body carries ids, fixed codes, counts and the names of the models the run called. This page prints
them in full.

**The trigger app talks to Bitbucket alone.** It reads a comment, its thread and the pull request, and starts the
pipeline; IronBee receives nothing of it, and holds no token of it.

Every call carries your API key in `X-API-Key`; the runner's calls carry its version in `User-Agent`
(`ironbee-runner/1.0.0`).

## Registration: `PUT /v1/code-review-repositories`

Made by `ironbee runner setup`, `add` and `check` for each repository they are given, and by you
([Setup](setup.md#1-register-the-repositories)). A run's start makes the repository's IronBee project itself when it
has none.

```json
{ "repository": { "provider": "bitbucket", "path": "acme/shop" } }
```

| Member | What it is |
|---|---|
| `repository.provider` | `bitbucket` |
| `repository.path` | `workspace/repository`, as the repository's address on bitbucket.org writes it |

A registration records no run, counts no developer and raises no alert. Its answer carries the project's id, the
licence's end date and the month's developers beside the limit, and whether the runner's version has a last day.

## Start: `POST /v1/code-review-runs`

Made by a run that found something due, before it clones or reads the change. A run with nothing due makes none; nor
does a command from someone who may not write, a run whose pull request was merged or declined, or one whose head was
pushed over.

```json
{ "repository": { "provider": "bitbucket", "path": "acme/shop" },
  "pullRequest": 412,
  "head": "9f2c4e1a7b3d5f60812a4c6e8b0d2f4a6c8e0b1d",
  "action": "review",
  "trigger": "bitbucket_pipelines",
  "developer": 169735042635783,
  "runner": { "version": "1.0.0" } }
```

| Member | What it is |
|---|---|
| `repository` | as in the registration |
| `pullRequest` | the pull request's number in the repository (`#412`) |
| `head` | the commit the run works on: the one its pipeline was started for |
| `action` | what the run found due, the first of: `retract` (a retract was asked), `review` (a conclusion is owed, or the head holds no review of the reviewer's), `respond` (words addressed to the reviewer in the conversation), `answer` (a reply on one of the reviewer's threads) |
| `trigger` | the CI: `bitbucket_pipelines` |
| `developer` | a number for the pull request's author (below); `null` when the author is a bot |
| `runner.version` | the runner's version |

**The author's number.** A Bitbucket account has no numeric id, so the runner derives one: the first six bytes of the
SHA-256 of the author's account uuid, as Bitbucket gives it (braces included), read as a whole number. IronBee uses it
to count the distinct developers of a month against your licence's limit, and for nothing else. It is not the account's
id, its name or its uuid, and IronBee cannot read any of them back from it. A Bitbucket author and a GitHub or GitLab
author are counted apart, even when the numbers match.

The answer carries what the run needs: the run's id, the depth setting with the size classes, the size bounds, the gates'
settings, the reviewer's settings, the paths to ignore, the console's rules and memories, the licence's end date and the
month's developers beside the limit, and whether the runner's version has a last day.

## Complete: `POST /v1/code-review-runs/<id>/complete`

Made at the end of every run that started, for its one action, whatever else it dealt with on the way. The body is
checked against its schema before it is sent.

```json
{ "status": "succeeded",
  "skip": null,
  "error": null,
  "round": 2,
  "read": "delta",
  "depth": "standard",
  "profile": "ironbee-self-hosted-standard",
  "customized": false,
  "classifier": "llm",
  "size": { "class": "M", "reviewableLines": 870, "files": 14 },
  "durationMs": 214000,
  "usage": { "calls": 31, "in": 412000, "out": 52000, "cacheRead": 0, "cacheWrite": 0,
             "byModel": [ { "model": "claude-sonnet-5-5", "calls": 27, "in": 380000, "out": 47000 },
                          { "model": "claude-opus-5-5", "calls": 4, "in": 32000, "out": 5000 } ] },
  "findings": { "posted": 5, "listed": 2, "open": 6, "fixed": 3, "dropped": 1, "blocking": 1,
                "bySeverity": { "critical": 0, "high": 1, "medium": 3, "low": 2 } },
  "answered": 0,
  "knowledge": { "applied": { "3f6c1d2e-8a4b-4c5d-9e0f-1a2b3c4d5e6f": 4 },
                 "cited": { "3f6c1d2e-8a4b-4c5d-9e0f-1a2b3c4d5e6f": 1 } } }
```

| Member | What it is |
|---|---|
| `status` | `succeeded`, `failed`, `cancelled` or `skipped` |
| `skip` | why a run was skipped: a gate (`asked_only`, `open_only`, `draft`, `bot`, `target_branch`, `skip_title_keyword`), `fork`, `too_large`, `already_reviewed`, `paused`, `not_addressed`, `newer_state` |
| `error` | why a run failed: `model_unreachable`, `model_refused`, `host_refused`, `clone_failed`, `reviewer_failed`, `timeout`, `configuration`. There is no message field |
| `round` | the review's round on the pull request |
| `read` | what a review read: `whole`, `delta` (what changed since the last round) or `nothing`; `null` when no review ran |
| `depth` | `quick`, `standard` or `deep` |
| `profile` | the profile the run used: `ironbee-self-hosted-quick`, `-standard` or `-deep` |
| `customized` | whether a value of your review file was applied |
| `classifier` | `llm` (your model answered the classifier's questions) or `jev` (Jev under your own key) |
| `size` | the size class (`S` to `XXXL`), the reviewable line count, and the file count |
| `durationMs` | the run's duration |
| `usage` | the model calls and their tokens in all, and for each model the run called (eleven at most, one for each task), under the name its task gave it |
| `findings` | the findings' counts: commented and listed in this round, and open, fixed, dropped and blocking on the pull request, the open ones by severity |
| `answered` | the number of questions and messages the run answered |
| `knowledge` | for each of the console's rules and memories the run used, by its id: how many reading calls carried it, and how many comments cite it |

Fields an action does not have are `null`. The schema is strict: integers, the closed lists above, the run's id, ids of
the console's rules and memories, and the models' names. A body with anything else is refused whole.

## The probe: `GET /v1/code-review-runs?limit=1`

The setup's probe, a run of the review pipeline on the default branch's head commit, reads one page of one run of
IronBee's list with the API key, to show the key answers. It sends no body and starts no run.

## With run reports off

With `IRONBEE_RUN_REPORTS` set to `false`, a run's start sends only this, and no complete is sent:

```json
{ "repository": { "provider": "bitbucket", "path": "acme/shop" },
  "developer": 169735042635783,
  "runner": { "version": "1.0.0" },
  "reports": false }
```

No pull request number, head, action or trigger, and nothing of how the run ended. IronBee keeps only that a run
started, to count the month's developers against your licence. The registration is the same. The console shows no pull
requests or runs for the repository, and says that its reports are off. Since no run says how it ended, every run that
starts counts its pull request's author, which can raise the month's developer count.

## What is never sent

File contents or diffs, file paths, branch names, titles, descriptions, commit messages, account ids, uuids, names of
authors and commenters, comments, finding texts, quotes, summaries, model prompts or replies, logs, error messages.

The models' names are the only strings a body carries beside ids, the repository's path and fixed codes. They are your
own configuration (the profile's, the review file's), bounded in number (eleven), length (200 characters) and alphabet
(letters, digits and `. _ : / @ -`).

## What else leaves your step, and where

- **Docker Hub** sees the image pulls Pipelines makes with your registry token. It is sent nothing about a repository.
- **Your model's endpoint** receives the model calls, and the extra headers of `IRONBEE_MODEL_HEADERS`, which go to that
  endpoint alone.
- **Jev's vendor**, only when you set your own Jev key, receives what IronBee's Jev guide lists, under your own account
  with it. None of that passes through IronBee.
- **Your rules repository and the review file** are read by the runner. Of them IronBee learns that the review file
  changed a value and the names of the models called, and nothing else.

## What stays with you

On Bitbucket Cloud, your code and your variables live with Atlassian, as they do without IronBee. A run on Atlassian's
runners computes there; a run on your own runner computes in your network, its log and its statuses still going to
Bitbucket. The clone, the model traffic, the rules repository's files, the review file, every record the reviewer
keeps (as hidden lines of its comments on the pull request), the status's text, the runs' working files (deleted with
the step's container), the pipelines' logs and the trigger app's log stay with you and Atlassian.

## Credentials

| Credential | Where it lives | Who can use it |
|---|---|---|
| the step's token | made by Bitbucket for each step, ends with it | the step; limited to its repository and its scopes |
| `IRONBEE_API_KEY`, the registry token, the model's key, the rules repository's token, the Jev key | secured variables of the repository (or of the workspace) | every pipeline of the repository (of the workspace), so whoever can push a branch there ([Identity](identity.md#what-a-pushed-branch-can-do)) |
| the trigger app's own token | Atlassian's, for the function of your own app | the function; and so whoever can deploy to the app: the members of its developer space who may deploy ([The trigger app](trigger-app.md#whose-power-it-is)) |
| your Atlassian API token at setup (`FORGE_API_TOKEN`) | the environment of the CLI's run | Forge's CLI, for that run |
| your `BITBUCKET_TOKEN` at setup | the environment of the CLI's run | the CLI, for that run; never stored by it, never sent to IronBee |

IronBee holds none of the Bitbucket credentials, the model's, the rules repository's, the Jev key or the trigger app's.
The API key is your account's one key, as on every host.

## Untrusted input

The reviewer reads a pull request and comments written by anyone who can write them.

- **The step's script is one fixed word,** `ironbee-runner`. A pull request's title, branch names and comments reach the
  runner through Bitbucket's API as data, never through the script.
- **Nothing in the repository is run.** The head is checked out only to be read; the model's tools only read, inside the
  checkout, and refuse a link that leaves it; the image's git runs no filter and no hook of the repository's. Nothing of
  the rules repository is run either.
- **What a model writes goes to the pull request and nowhere else.** Before it is posted, every Markdown image in it
  (inline, by reference, or in its shortcut form) is left as its text and its address in plain sight, since Bitbucket
  shows an image a comment names and so fetches its address. Raw HTML is shown as text on Bitbucket and no diagram is
  rendered, so nothing else in a comment loads an address. A link stays a link.
- **Who is obeyed.** A command only from someone with the write or admin permission, a reply on the reviewer's thread
  only from people who count, and a comment of an app user's starts nothing.
- **The trigger app reads a comment's text only to match the reviewer's name and marker**, and writes none of it
  anywhere: what it sends Bitbucket is a pull request's number, its branches' names and two commit ids.

A prompt injection can therefore at most make a review or an answer wrong, or make it quote the repository's own code
into the repository's own pull request. Where the step may connect is your network's policy.
