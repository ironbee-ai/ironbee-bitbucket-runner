# Troubleshooting

Where to look first:

- **The pull request's builds.** `Code Review Result` is the reviewer's status: `FAILED`, `SUCCESSFUL`, or a
  `SUCCESSFUL` `neutral` whose description says why nothing was reviewed. `Pipeline - custom: ironbee-code-review` is the
  review pipeline's own: in progress while a run is under way or waits its turn, then the run's result
  ([Merge checks](merge-checks.md)).
- **The repository's Pipelines.** Every run is a pipeline of the custom pipeline `ironbee-code-review`; its log says
  what the runner read and decided, and a problem starts with `error:`, `warning:`, `failed:` or `IronBee`.
- **The trigger app's log**, for a comment that started nothing: `forge logs -e production` (the app is deployed to
  production alone), signed in to Forge as one of the app's developers, in a directory holding its `manifest.yml` with
  its id ([below](#a-comment-started-nothing)).
- **`ironbee runner check`**, which reads the whole setup, and `ironbee runner check --probe`, which runs the probe
  ([Setup](setup.md#checking-ironbee-runner-check)).

**The step's exit.** The step exits 0 when the run ended by its own doing, whatever it found, a configuration error the
runner can tell included: nothing below shows a failed build unless it says so. It exits 1 where a pass would say more
than is true: a head whose review was posted and could not be concluded; a head owed a conclusion that the run could not
write; a start with no pull request on a pull request's source branch; and a run whose reads of Bitbucket failed before
it knew whether its head is owed a conclusion (Bitbucket down, a second 429), since a pass there could lift a dead run's
hold. The probe fails for anything it finds wrong.

## No run at all

| What you see | Why | What to do |
|---|---|---|
| no pipeline and no status of the reviewer's on a pull request | the block is missing on the pull request's source branch: a pull request's events run the file its source branch brings | merge the default branch, which holds the block, into the branch; its next push or edit starts a run |
| no pipeline for any pull request of the repository | Pipelines is off, or the block is not on the default branch yet (a setup by pull request waits for its merge) | `ironbee runner check`; turn Pipelines on ([Setup](setup.md#2-pipelines)) |
| a head of a pull request has no review and no status of the reviewer's | no pipeline was started for it: an event Bitbucket raised no pipeline for | its next event (a push, an edit, a comment through the trigger app) starts one; saving the description is such an edit |
| no pipeline starts in the workspace | the workspace has spent its plan's build minutes | wait for the plan's month to turn, or move the runs to a runner of yours ([Where the step runs](compute.md#build-minutes)) |
| nothing on a pull request from a fork | Bitbucket runs no pipeline for a fork's pull request | nothing: forks' pull requests are not reviewed |

## The pipeline fails before the runner starts

The pipeline's log ends before any line of the runner's.

| What you see | Why | What to do |
|---|---|---|
| the image cannot be pulled, on every pull request | `IRONBEE_REGISTRY_TOKEN` missing or wrong, the token revoked, or the registry down | set the variable again (`ironbee runner setup` with `IRONBEE_REGISTRY_TOKEN` writes it where it is missing); `ironbee runner check --probe` finds it. Where builds block, this holds the merges until it is put right |
| the step lists a scope Bitbucket does not know, or the step has no token | the block's `auth` was changed, or your runner is older than 6.1.0 | the block as released (`ironbee runner setup --update`); a runner of 6.1.0 or later ([Where the step runs](compute.md)) |
| the step waits, and no runner takes it | `runs-on` names labels no runner of yours has, or that runner is offline | the runner's labels, and that it is online |
| the step ran out of memory | the step's default size | `size: 2x` on the step, at twice the minutes |
| the file is refused | a change of `bitbucket-pipelines.yml` Bitbucket does not take | the pull request that changed it shows Bitbucket's words; `ironbee runner check` reads the block |

## A run that ends with nothing done

- **Nothing was due.** An edit of the title on a head already concluded, a comment that was not for the reviewer, a
  reply the reviewer had already answered: the run reads the pull request and ends, writing nothing and calling no one.
- **The pull request was merged or declined while the run waited:** it ends at its first read.
- **The head was pushed over:** a run works on the commit its pipeline was started for, and ends at once when the pull
  request's head has moved on. The newer head has its own run, queued behind this one.
- **Two runs of one pull request:** the second waits in the pull request's queue, and then finds what the first wrote.
- **A command from someone who may not command:** the run reads the person's permission, ends before any call to
  IronBee, and writes nothing.

## A start on a branch fails

**Run pipeline** on a branch, or a start through the API with a branch as its target, is no pull request's run. Where
the branch is the source of an open pull request of the repository, its status is the very record that pull request's
runs write: such a start does no work and **fails** (the step exits 1), its log saying how a pull request's run is
started, since a pass written there by a run that reviewed nothing could let a head through. The pull request's next
run sets the pipeline's status right. On any other branch it ends with nothing done.

To review a pull request again, ask in it: `@ironbee-ai review`, or push.

## IronBee refused the run, or could not be reached

The log says `IronBee refused the run (<code>): <sentence>`, or that IronBee gave no answer. Nothing is reviewed, the
step exits 0, and the head gets the sentence as its `neutral`, by the status's rule. **Where the head is owed a
conclusion** (a dead run posted a review and did not conclude it), the step fails instead and the hold the dead run left
stays, until a run can write the conclusion.

| `neutral` | Code | What to do |
|---|---|---|
| IronBee's self-hosted review is not enabled for this account; contact IronBee. | `SELF_HOSTED_RUNNER_NOT_ENABLED` | contact IronBee |
| IronBee's reviews are suspended for this account; contact IronBee. | `SELF_HOSTED_RUNNER_SUSPENDED` | contact IronBee |
| The licence for IronBee's self-hosted review has ended; contact IronBee to renew it. | `SELF_HOSTED_RUNNER_LICENCE_ENDED` | renew the licence; the next event is reviewed |
| This version of the IronBee runner is no longer served; move … to `<version>`. | `RUNNER_VERSION_UNSUPPORTED` | move the block to that release: `ironbee runner setup --update --version <version>` |
| IronBee's cloud reviews this repository; turn its code review off in the console before the runner reviews it. | `REPOSITORY_REVIEWED_BY_CLOUD` | turn the repository's code review off in the console |
| Missing or invalid credentials | `UNAUTHORIZED` | `IRONBEE_API_KEY` is wrong, or a rotated key past its grace period |
| IronBee could not be reached, so this pull request was not reviewed. | — | check that the step can reach IronBee's API (`api.service.ironbee.ai`, or the address in `IRONBEE_API_URL`), then re-run the pipeline, or ask `@ironbee-ai review` |

A `FAILED` an earlier review wrote stays on its head: a refused run never weakens it.

## The `neutral` names a setting or the pull request

| Why | What to do |
|---|---|
| automatic reviews are off for this repository (`autoReview: asked`) | ask `@ironbee-ai review`, or change the setting |
| this repository's pull requests are reviewed when they are opened, not on every push (`autoReview: open`) | `@ironbee-ai review` reviews this head |
| the pull request is a draft (`reviewDrafts` off) | mark it ready: that edit starts a run, which asks the gate again |
| a bot opened the pull request (`reviewBotPullRequests` off) | turn the setting on to review them |
| the target branch is none of the branches this repository's reviews are for (`targetBranches`) | the console's setting, or `IRONBEE_TARGET_BRANCHES` for a repository without a project |
| the title says not to review it (`skipTitleKeywords`) | as it says |
| automatic reviews of this pull request are paused (`@ironbee-ai pause`) | `@ironbee-ai resume`, or `@ironbee-ai review` for this head |
| the pull request is too large | split the change |
| a newer release of the runner wrote this pull request's state | move the block forward to that release or a later one: `ironbee runner setup --update` |
| a configuration error ([below](#configuration-errors)) | fix what the pipeline's log names |
| the review did not run to its end | read the log's `failed:` line ([below](#the-run-failed)); a re-run of the pipeline, or `@ironbee-ai review`, reviews this head |

A `neutral` an earlier run wrote settles nothing: the next run on that head asks the gates again (a draft marked ready,
a setting changed, a variable put right), and reviews the head when they let it. A review someone asks for by a
command passes every gate but the one for forks; the conversation's commands and questions are answered whatever
becomes of the review.

## Configuration errors

A variable the runner needs is missing or wrong (the API key, the model's provider or key, a value that does not
decode). The log says `error: <variable>: <why>`, naming the variable and never its value; nothing is read; the head
gets a `neutral` that says the configuration keeps the review from running; the step exits 0, since the review did not
run and no merge is held for it. Where the head is owed a conclusion, the step fails and the hold stays.

| Variable | Why |
|---|---|
| `IRONBEE_API_KEY` | missing |
| `IRONBEE_MODEL_PROVIDER` | missing, or not `anthropic`, `bedrock` or `openai` |
| `IRONBEE_MODEL_KEY` | no key without `IRONBEE_MODEL_URL`: a provider's own endpoint needs one |
| `IRONBEE_MODEL_NAME` | `openai` with `IRONBEE_MODEL_URL` and no model name; or a name that is not 1 to 200 letters, digits and `. _ : / @ -` |
| `IRONBEE_MODEL_HEADERS` | a line that is neither blank nor a header's `name=value` (the error names the line's number, never its text) |
| `IRONBEE_MODEL_CA_CERTIFICATE` | no certificate in it |
| `AWS_REGION` | missing on `bedrock`, or not a region's name |
| `IRONBEE_MODEL_MAX_OUTPUT` | not a whole number of 1 or more |
| `IRONBEE_RUN_REPORTS` | neither `true` nor `false` |
| any variable given as `base64:` | the rest is not base64, or does not decode to text ([Setup](setup.md#3-the-variables)) |

## The run failed

The log says `failed: <code>: …`, and the run reports the code to IronBee.

| Code | What happened | What to do |
|---|---|---|
| `model_unreachable` | the model's endpoint could not be reached, or gave no answer | `IRONBEE_MODEL_URL`, the network between the step and the endpoint, `IRONBEE_MODEL_CA_CERTIFICATE`, and `runs-on` for a model inside your network |
| `model_refused` | the endpoint answered no: a wrong key, a missing header, a model it does not serve | `IRONBEE_MODEL_KEY`, `IRONBEE_MODEL_HEADERS` and the model's name; an output budget the model refuses is lowered with `IRONBEE_MODEL_MAX_OUTPUT` |
| `host_refused` | Bitbucket refused a write | the block's scopes as released |
| `clone_failed` | the repository could not be cloned | re-run the pipeline; the block's `read:git:bitbucket` scope |
| `timeout` | the run ran out of time | re-run the pipeline; the review file's timeouts |
| `reviewer_failed` | anything else | the log's traceback; re-run the pipeline |

**Before its review was posted**, a failed run writes a `neutral` where the head holds nothing of the reviewer's, and
the step exits 0, once its first reads of Bitbucket have told it whether its head is owed a conclusion; a run whose
first reads fail exits 1 ([below](#bitbucket-answers-429)). **After it**, or while it concluded, the step exits 1 and the review pipeline's own status is a failed
build: the next run on that head (an edit's, a comment's, a re-run) writes the conclusion from the texts before anything
else. A conclusion the run tried to write and Bitbucket refused is such a case too.

**A run killed or timed out** leaves its own status failed or stopped, as Bitbucket has it. The next run on that head
removes the finding comments the killed run left with no review body after them (one someone replied to stays, and the
next round adopts it), and reviews the head, or concludes a review that was posted
([Merge checks](merge-checks.md#the-pipelines-own-status)).

## The pull request holds 200 comments

Bitbucket refuses a pull request's 201st comment. A round whose comments are refused takes them back and is published
as its body alone, the findings listed in it, and says so. Where not even that comment can be made, the run has failed
before its review was posted: a `neutral`, and the log says the pull request takes no more comments.

## Bitbucket answers 429

The runner waits a minute once, as on every host; a second 429 fails the run. Where it comes in the run's first reads
of Bitbucket, before the run knows whether its head is owed a conclusion, the run writes nothing and the step exits 1:
the review pipeline's own status is a failed build, which holds the merge where builds block, until the next run on
that head (a push, an edit, a comment, a re-run) reads it through. The same holds for any failure of those first reads,
Bitbucket being down among them. Later in the run, a second 429 fails it by the rules [above](#the-run-failed).

## A comment started nothing

The trigger app's log (`forge logs -e production`) has a line for each comment: the workspace's, the repository's, the pull request's
and the comment's ids, and the outcome.

| Outcome | Meaning |
|---|---|
| `started` | the pipeline was started (`build` is its number); `why` is `addressed`, `our thread`, or `deep thread` (a reply more than ten replies below its thread's first comment, taken unread: the run reads the thread whole) |
| `not for us` | the comment neither addresses `@ironbee-ai` (outside quoted lines and code) nor answers a thread of the reviewer's |
| `not a person` | an app user's comment, the reviewer's own among them |
| `pull request not open` | merged or declined: a pull request's pipeline needs its source branch |
| `pull request from a fork` | Bitbucket runs no pipeline of the repository's for it |
| `start refused` | Bitbucket refused the start: `status` and `error`, Bitbucket's code, say why. A repository whose source branch's file has no `ironbee-code-review` pipeline is refused so |
| `comment unread`, `thread unread`, `pull request unread` | a read failed (`status`); the comment waits for the pull request's next run |
| `failed` | a call failed (`error` names its kind) |

No line at all: the app is not installed on the workspace, or not deployed to production (`forge install list`, and
`ironbee runner check`), or Bitbucket's delivery is late: it may take up to three minutes. A delivery that is lost, or a
start that is refused, leaves the comment for the pull request's next run; nothing else changes.

A comment a person publishes later from a pending review is due when a run sees it.

## Warnings in the pipeline's log

| Line | What to do |
|---|---|
| `warning: this account has more developers this month than its licence covers; reviews go on, and IronBee will be in touch` | nothing: reviews go on |
| `warning: the licence for IronBee's self-hosted review ends soon; renew it to keep pull requests reviewed` | renew the licence |
| `warning: runner <version> is served until <day>; move … to <version> before then` | move the block to that release before that day |
| `warning: the rules repository <path> could not be read (…): <why>; the review goes on without it` | `IRONBEE_KNOWLEDGE_REPOSITORY`, `IRONBEE_KNOWLEDGE_REF`, `IRONBEE_KNOWLEDGE_TOKEN` (a repository access token of the rules repository, with read access). On a Premium workspace that limits its private content to listed addresses, a step on Atlassian's runners at an address the list does not hold is refused that read (a 403): run the step on a runner of yours at a listed address ([Where the step runs](compute.md)) |
| `IronBee: the complete did not land: <why>` | nothing: the run stands as it ended |

## A newer state format

Moving the block back across a change of the format of the state the reviewer keeps in its comments (which only a
major release makes) leaves the pull requests the newer release wrote unreviewed until you move forward again: such a
run writes nothing on the pull request, ends as skipped (`newer_state`), says in the pipeline's log to move the block
forward, and leaves a `neutral`.

## The setup command

| What it says | What to do |
|---|---|
| it names a scope your `BITBUCKET_TOKEN` lacks | make a token with that scope, and run the command again; nothing was changed |
| `IronBee refused <repository> (<code>): …` | the registration was refused ([above](#ironbee-refused-the-run-or-could-not-be-reached)); nothing was changed on Bitbucket |
| Pipelines could not be turned on | Bitbucket asked for more than the token (such as two-step verification): turn it on in **Repository settings** > **Pipelines** > **Settings**; the command went on |
| it left the trigger app out, naming Node, npm, Forge's CLI, a sign-in or the developer space | install or set what it names, and run the command again: it sets the app up and changes nothing else |
| the trigger app is recorded and was not verified | sign in to Forge as one of the app's developers to have it checked and repaired |
| the probe failed, with the pipeline's log | the log says what: a registry token that cannot pull, a runner too old, a block whose scopes were cut, a wrong key |
| it opened a pull request and did not probe | the block reaches the default branch with that pull request's merge: run `ironbee runner check --probe` then |

A command that fails midway leaves what it made. Run it again: it reads what exists and goes on.
