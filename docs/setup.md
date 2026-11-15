# Setup

This guide takes your bitbucket.org repositories from nothing to reviewed pull requests. IronBee's CLI does the whole
setup with one command, `ironbee runner setup`; every step it takes is also written out below for doing by hand. A
setup made by hand and one made by the command are the same objects, and `ironbee runner check` reads either.

## What you need

From IronBee:

- **The self-hosted runner enabled on your IronBee account.** Its licence has an end date and a developer limit.
- **Your account's API key.** IronBee's API takes it in `X-API-Key`. It is your account's key: it can do on IronBee's
  API everything that key can do, and this feature adds no narrower one.
- **A registry token.** IronBee's runner image is in a private repository on Docker Hub, and IronBee gives each
  customer a read-only token for it. Being able to pull the image entitles you to nothing by itself: every run still
  asks IronBee whether it may run.

From your side:

- repositories on bitbucket.org, and the **admin** permission on each: turning Pipelines on and writing its variables
  need it. Writing the workspace's variables instead (`--workspace-variables`) needs a **workspace admin**.
- a model, and its key where it needs one.
- Atlassian's runners, or a Bitbucket runner of your own ([Where the step runs](compute.md)).
- for comments, the trigger app ([The trigger app](trigger-app.md)): a **workspace admin** (Atlassian lets only an admin
  install an app), Node.js 22 or later, Atlassian's Forge CLI (`npm install -g @forge/cli`), and a **developer space**
  in Atlassian's developer console, made once in the browser. Read [what it holds](trigger-app.md#whose-power-it-is)
  before you set it up.

## What gets made

| Object | Where | What for |
|---|---|---|
| **Pipelines** turned on | each reviewed repository | the review runs in the repository's own Pipelines |
| the **variables** | each reviewed repository (or the workspace) | the API key, the registry token, the model's settings and key ([Variables](#3-the-variables)) |
| **the block** | each reviewed repository's `bitbucket-pipelines.yml` | the custom pipeline `ironbee-code-review` and the two triggers that start it |
| a **project in IronBee** | the IronBee console | its settings, rules and memories, and the list of its pull requests and runs |
| **the trigger app** | your Atlassian developer space; its production environment; installed on the workspace | starts the pipeline for a comment that is for the reviewer |
| `IRONBEE_TRIGGER_APP` | a variable of the workspace | records the app and its release, so that a later setup finds it and makes no second one |

Nothing else of the file changes: your own pipelines, definitions and triggers stay as they are.

## With the command

### Install the CLI

```sh
npm install -g @ironbee-ai/cli
```

It needs Node.js 22 or later. Run the setup on your own machine: the command acts as you, and nothing of your sign-in
reaches IronBee.

### Sign in

The command acts as you, with **`BITBUCKET_TOKEN`**: an Atlassian API token of yours with Bitbucket scopes, made at
id.atlassian.com for the setup, with the nearest expiry date. It needs the repository's and its pull requests', the
pipelines' and their variables', and the repository's settings: `read:repository:bitbucket`,
`write:repository:bitbucket`, `admin:repository:bitbucket`, `read:pullrequest:bitbucket`,
`write:pullrequest:bitbucket`, `read:pipeline:bitbucket`, `write:pipeline:bitbucket` and `admin:pipeline:bitbucket`.
Before it changes anything, the command tries what each step needs and names any scope the token lacks. It neither
stores the token nor sends it to IronBee; revoke it when the setup is done.

The trigger app's step signs in to Forge from **`FORGE_EMAIL`** and **`FORGE_API_TOKEN`**: your Atlassian account's
email and an API token of it for Forge (or a sign-in Forge's CLI already holds, from `forge login`). Revoke that token
too when the command has ended.

### The secrets

Each comes from its environment variable, or is asked for and typed unseen. The command writes none of them to disk,
prints none of them, and sends none to IronBee: they go from your machine into secured Pipelines variables.

| Environment variable | What | When |
|---|---|---|
| `IRONBEE_API_KEY` | your account's API key | always: the registrations need it |
| `IRONBEE_REGISTRY_TOKEN` | the registry token | asked when the repository has no `IRONBEE_REGISTRY_TOKEN` |
| `IRONBEE_MODEL_KEY` | your model's key | asked when the repository has no `IRONBEE_MODEL_KEY`; empty for an endpoint that takes none |
| `IRONBEE_MODEL_HEADERS` | extra headers for your model's endpoint, one `name=value` a line | only from the environment |
| `IRONBEE_KNOWLEDGE_TOKEN` | a read-only repository access token for the rules repository | only from the environment |
| `IRONBEE_JEV_KEY` | Jev with your own key | only from the environment |

A variable that exists is left as it is: a secured variable cannot be read back, so the command cannot tell whether it
differs.

### Run it

```sh
export BITBUCKET_TOKEN IRONBEE_API_KEY IRONBEE_REGISTRY_TOKEN IRONBEE_MODEL_KEY FORGE_EMAIL FORGE_API_TOKEN
ironbee runner setup --host bitbucket \
  --repos acme/shop,acme/payments \
  --model-provider anthropic \
  --developer-space <your developer space's id>
```

Inside a clone of a bitbucket.org repository, `--host bitbucket` may be left out: the command takes the host from the
directory's git remote.

| Flag | What |
|---|---|
| `--host bitbucket` | this host (else the directory's git remote, else asked) |
| `--repos <list>` | the repositories to review, `workspace/repository`, separated by commas |
| `--model-provider`, `--model-url`, `--model-name`, `--model-prefix`, `--model-max-output`, `--aws-region` | the model's settings |
| `--model-ca-certificate <file>` | a PEM file: the private authority that signed your model endpoint's certificate |
| `--knowledge-repository <workspace/repository>`, `--knowledge-ref <ref>` | the rules repository |
| `--ignore-paths`, `--target-branches`, `--skip-title-keywords` | for a repository left without a project in IronBee; each a list separated by commas |
| `--run-reports false` | a run tells IronBee only that it started |
| `--workspace-variables` | the workspace's variables instead of each repository's (a workspace admin; read by every pipeline of the workspace) |
| `--runs-on <label,…>` | your own Bitbucket runner's labels, written as the step's `runs-on`: `self.hosted,linux` for an `amd64` runner, `self.hosted,linux.arm64` for an `arm64` one ([Where the step runs](compute.md)) |
| `--version <release>` | the release the block names, `1.0.0` (or a pre-release's whole name, `1.0.0-rc.7`); the latest release when not given |
| `--update` | move a block that is there, and the trigger app, to the latest release or to `--version`'s |
| `--direct` | commit to the default branch instead of opening a pull request, where that is allowed (below) |
| `--no-trigger-app` | leave the trigger app out |
| `--developer-space <id>` | the Atlassian developer space the trigger app is registered in |
| `--trigger-app-name <name>` | the trigger app's name, when not `ironbee-runner-trigger` |
| `--source <directory>` | a local copy of this repository's layout in place of a release's download, for a pre-release under test |

### What it does, in this order

Each step first reads what exists, and changes only what is missing or differs. So the command can be run again after
a failure, and `add` and `check --fix` are the same steps.

1. **The registrations.** Each repository is registered with IronBee (`PUT /v1/code-review-repositories`), which
   makes its project in the console. A refusal (the feature not enabled, the licence ended or suspended, a repository
   IronBee's cloud product reviews) ends the command before anything is changed on Bitbucket.
2. **Pipelines.** Turned on for a repository that has it off, and said so. Bitbucket may refuse that call (it can ask
   the account for two-step verification): the command then tells you to turn it on in Bitbucket's pages
   ([by hand](#2-pipelines)) and goes on.
3. **The variables** it was given, as the repository's (or, with `--workspace-variables`, the workspace's), secured
   where the [table](#3-the-variables) says. A variable that exists is left as it is. A value of more than one line is
   written as `base64:` followed by the value in base64.
4. **The file.** The block at the release (the latest, or `--version`'s) is added to `bitbucket-pipelines.yml` as
   text: the custom pipeline under `pipelines.custom`, a condition under each of the two trigger types, each made where
   missing, in your file's own indentation; every byte outside the lines it adds stays as it was. The command then
   reads its result back and goes on only when every pipeline, trigger, definition and setting the file held is in it
   unchanged and the block is as released.
   - A file that exists is always changed **by a pull request**: a branch of its own and the pull request opened, which
     your team reads, and whose own pipelines show whether Bitbucket takes the file.
   - `--direct` commits to the default branch only a file that did not exist, or a block that is there and moves to
     another release (`--update`).
   - A block that is there is otherwise left as it is. `--update` replaces its lines whole with the release's, keeping
     only the step's `runs-on`.
5. **The trigger app**, once per workspace ([below](#the-trigger-app-step)).
6. **The report:** what it made, kept and found, never a secret, and what gates a merge in each repository, which it
   does not set ([Merge checks](merge-checks.md)).

Then **the probe**, for each repository whose default branch holds the block ([below](#the-probe)). A setup that
opened a pull request probes after the merge: run `ironbee runner check --probe` then.

### The trigger app step

Before it registers anything, the command says whose the app will be and what that account can then do
([The trigger app](trigger-app.md#whose-power-it-is)), and asks you to go on. Then:

1. It fetches the release's `trigger-app/` files into a temporary directory and installs the app's one dependency
   there from its lockfile, with `npm ci --ignore-scripts`: no package's install script runs on your machine.
2. `forge register <name> -s <developer space> -y` registers the app in the developer space, and at once the command
   writes `IRONBEE_TRIGGER_APP`, a variable of the workspace that records the app's id and the release:
   `{"app":"ari:cloud:ecosystem::app/<uuid>","release":"1.0.0"}`. A run of the command that stops after this finds
   the app again and makes no second one.
3. `forge deploy -e production --non-interactive` deploys the source to the app's production environment.
4. `forge install -e production -p Bitbucket -s bitbucket.org/<workspace> --confirm-scopes --non-interactive`
   installs it on the workspace: that is your consent, as the workspace's admin, to its three scopes.
5. `forge install list --json` reads the installations back; the app is reported as set up only when the workspace is
   among them.

On a later run, signed in to Forge as one of the app's developers, the command reads the same and repairs what is
missing (the deployment, the installation); `--update` deploys a later release's source and writes the release into
the variable. Without such a sign-in it changes nothing of the app and says that the app is recorded and was not
verified. Where Node, npm, Forge's CLI, a sign-in or the developer space is missing, the command says which and goes on
without the app.

### The probe

The command starts the custom pipeline on the default branch's head commit, with the commit as its target and no
branch, and waits for its end. Such a run is the probe: it reads the repository with the step's token and IronBee's
list of runs with the API key, compares the scopes the token carries with the four the block lists, writes nothing,
and fails with what is wrong. The command judges it by the pipeline's result alone. So a wrong registry token (the
image is not pulled), a runner of yours that is too old, a block whose scopes were cut, or a wrong key is found now,
not at the first pull request. No developer is counted.

The probe's status is a record of its own on that commit, beside any pull request's: where the default branch's head
is also a pull request's head, it shows there as one more build, and a failed probe shows a failed build there until
one succeeds.

### More repositories: `ironbee runner add`

```sh
ironbee runner add acme/billing --host bitbucket
```

The same steps for the repositories named; the trigger app is the workspace's and is set up once.

### Checking: `ironbee runner check`

```sh
ironbee runner check --host bitbucket --repos acme/shop,acme/payments
```

It changes nothing without `--fix`. It reads, for each repository: the block on the default branch and its release
against the latest; that Pipelines is on; that the variables it needs exist (by name); the registration; the trigger
app as its step reads it (recorded and, signed in to Forge, verified; its release against the latest); and, as
information, whether the repository's merge checks would hold a merge on a failed build. `--fix` repairs what the
steps make; `--probe` runs the probe.

### What stays yours

- the developer space in Atlassian's developer console, and who may deploy to it ([The trigger app](trigger-app.md));
- a Bitbucket runner of your own, where you need one ([Where the step runs](compute.md));
- the merge checks ([Merge checks](merge-checks.md));
- a rules repository's content, and its repository access token;
- removing the trigger app: Forge's own `forge uninstall`.

## By hand

The same objects, in the same order. Where a step names an object, use that name: `ironbee runner check` finds the
objects by them. The API calls below take your Atlassian account's email and an API token of yours
(`-u "$EMAIL:$BITBUCKET_TOKEN"`); keep tokens out of your shell's history: `read -rs BITBUCKET_TOKEN`, then paste.

### 1. Register the repositories

Optional, and recommended: a registered repository has its project in the console before its first pull request, so
its settings are in place for its first review. A repository not registered is registered by its first run.

```sh
curl --fail-with-body -X PUT https://api.service.ironbee.ai/v1/code-review-repositories \
  -H "X-API-Key: $IRONBEE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"repository": {"provider": "bitbucket", "path": "acme/shop"}}'
```

The path is `workspace/repository`, as the repository's address on bitbucket.org writes it. With an `IRONBEE_API_URL`
from IronBee, use that address in place of the default one. The answer:

```json
{ "project": { "id": "<uuid>", "created": true },
  "noProject": null,
  "licence": { "developers": { "limit": 50, "used": 41 }, "endsAt": "2027-11-13" },
  "runner": { "supportedUntil": null, "moveTo": null } }
```

`created` is `false` when the project was already there; the call may be repeated. It is refused, and nothing changes,
when the self-hosted runner is not enabled on the account (`SELF_HOSTED_RUNNER_NOT_ENABLED`), when the account is
suspended (`SELF_HOSTED_RUNNER_SUSPENDED`), when the licence has ended (`SELF_HOSTED_RUNNER_LICENCE_ENDED`), and when
IronBee's cloud product reviews the repository (`REPOSITORY_REVIEWED_BY_CLOUD`): two reviewers on one pull request
would both post, so turn its code review off in the console first.

**A repository left without a project.** `noProject` names why (`project_limit`, `project_archived`, `name_taken`),
and `project` is `null`. Such a repository is still reviewed, with your account's settings, and with its per-project
settings taken from `IRONBEE_IGNORE_PATHS`, `IRONBEE_TARGET_BRANCHES` and `IRONBEE_SKIP_TITLE_KEYWORDS`. Its runs are
in no project's list in the console.

### 2. Pipelines

In the repository, **Repository settings** > **Pipelines** > **Settings**: **Enable Pipelines**. A repository that
never had Pipelines on has it off. Bitbucket's API can turn it on too (`PUT …/pipelines_config` with
`{"enabled": true}`), and may ask the account for two-step verification instead; the page always works.

### 3. The variables

**Repository settings** > **Pipelines** > **Repository variables**, for each (or **Workspace settings** > **Pipelines**
> **Workspace variables**, which every pipeline of every repository of the workspace reads: keep the secrets in each
repository's own unless you mean that).

| Name | Value | Secured |
|---|---|---|
| `IRONBEE_API_KEY` | your account's API key | yes |
| `IRONBEE_REGISTRY_TOKEN` | the registry token | yes |
| `IRONBEE_MODEL_PROVIDER` | `anthropic`, `bedrock` or `openai` | no |
| `IRONBEE_MODEL_KEY` | your model's key, when your endpoint takes one | yes |
| `IRONBEE_MODEL_HEADERS` | extra headers for your model's endpoint, one `name=value` a line, as `base64:` (below) | yes |
| `IRONBEE_MODEL_URL`, `IRONBEE_MODEL_NAME`, `IRONBEE_MODEL_PREFIX`, `IRONBEE_MODEL_MAX_OUTPUT`, `AWS_REGION` | the model's endpoint, one model for every task, Bedrock's inference profile prefix, the most output tokens a turn may ask for, Bedrock's region | no |
| `IRONBEE_MODEL_CA_CERTIFICATE` | the certificates (PEM) of the private authority that signed the endpoint's certificate, as `base64:` | no |
| `IRONBEE_JEV_KEY` | Jev with your own key | yes |
| `IRONBEE_KNOWLEDGE_REPOSITORY`, `IRONBEE_KNOWLEDGE_REF` | the rules repository (`workspace/repository`), and a branch or a tag of it | no |
| `IRONBEE_KNOWLEDGE_TOKEN` | a repository access token of the rules repository, with read access: the step's token reaches its own repository alone | yes |
| `IRONBEE_IGNORE_PATHS`, `IRONBEE_TARGET_BRANCHES`, `IRONBEE_SKIP_TITLE_KEYWORDS` | for a repository left without a project in IronBee, one entry a line, as `base64:` | no |
| `IRONBEE_API_URL` | IronBee's API address, when IronBee gave you another than the default | no |
| `IRONBEE_RUN_REPORTS` | `false`: a run tells IronBee only that it started | no |

**A value of more than one line.** A Pipelines variable holds no line break. Give such a value as `base64:` followed
by the value in base64, on one line; the runner decodes it before anything reads it, and a value that does not decode
is a configuration error that names the variable:

```sh
printf 'base64:%s\n' "$(base64 < ca.pem | tr -d '\n')"
```

The line it prints is the value. A value that does not begin with `base64:` is read as it is.

### 4. The block

Add the block of the release you choose to your repository's `bitbucket-pipelines.yml`, on the default branch, by a
pull request of your own. The release's block is [`templates/bitbucket-pipelines.yml`](../templates/bitbucket-pipelines.yml)
at its tag (`v1.0.0`), with the image's digest and the release's name in it; `release.json` at that tag names the same.

- **A file with pipelines of its own** keeps them: the block is one more entry under `pipelines.custom`, and one more
  condition under `triggers.pullrequest-created` and `triggers.pullrequest-updated` (a file takes twenty conditions a
  type). A file with no `custom:` under `pipelines:` gains one; one with no `triggers:` gains it whole.
- **Leave the block's lines as they are**, the comment on the pipeline's line included: it names the release for
  people and for `ironbee runner check`. The pipeline's name, the concurrency group and the scopes are part of the
  release.
- **Your own runner:** replace the comment `# runs-on: …` with the step's `runs-on`, listing your runner's labels
  ([Where the step runs](compute.md)).
- A branch cut before the block reached the default branch has no block, and its pull request starts nothing until
  the branch takes the default branch in: a pull request's events run the file its source branch brings.

Bitbucket validates the file when a pipeline starts: the pull request that adds it shows whether Bitbucket takes it.

### 5. The trigger app

The [trigger app](trigger-app.md) makes comments start a run. Read [whose power it is](trigger-app.md#whose-power-it-is)
first. As a workspace admin who is a member of the developer space, with Forge's CLI signed in (`forge login`, or
`FORGE_EMAIL` and `FORGE_API_TOKEN` in the environment):

1. Fetch the release's four files, as `release.json` lists them, at the release's tag, into a directory of their own:

   ```sh
   mkdir ironbee-runner-trigger && cd ironbee-runner-trigger
   for f in manifest.yml package.json package-lock.json src/index.js; do
     curl --fail --create-dirs -o "$f" "https://raw.githubusercontent.com/ironbee-ai/ironbee-bitbucket-runner/v1.0.0/trigger-app/$f"
   done
   npm ci --ignore-scripts
   ```

   `npm ci --ignore-scripts` installs the one dependency, `@forge/api`, from the lockfile, running no package's
   scripts.
2. Register it, and record it **at once**:

   ```sh
   forge register ironbee-runner-trigger -s <developer space id> -y
   ```

   Forge writes the app's id into `manifest.yml` (`app.id`, `ari:cloud:ecosystem::app/<uuid>`). Add the workspace's
   variable `IRONBEE_TRIGGER_APP` (**Workspace settings** > **Pipelines** > **Workspace variables**, not secured), one
   line of JSON with that id and the release:

   ```json
   {"app":"ari:cloud:ecosystem::app/<uuid>","release":"1.0.0"}
   ```

   Without it, `ironbee runner setup` would later take the app for missing and register a second one.
3. Deploy it to the production environment, and install it on the workspace:

   ```sh
   forge deploy -e production --non-interactive
   forge install -e production -p Bitbucket -s bitbucket.org/<workspace> --confirm-scopes --non-interactive
   forge install list --json
   ```

   The last command lists the app's installations: the workspace must be among them.
4. Revoke the Atlassian API token you signed in to Forge with, if you made one for this.

A later release is deployed the same way, from that release's files with the recorded id in `manifest.yml`
(`forge deploy -e production`), and its name written into `IRONBEE_TRIGGER_APP`.

### 6. Check it

Run `ironbee runner check --probe` ([above](#checking-ironbee-runner-check)). Without the CLI, start the probe
yourself, on the default branch's head commit with a commit target, once the block is on the default branch:

```sh
curl --fail-with-body -X POST -u "$EMAIL:$BITBUCKET_TOKEN" -H "Content-Type: application/json" \
  "https://api.bitbucket.org/2.0/repositories/acme/shop/pipelines/" \
  -d '{"target": {"type": "pipeline_commit_target", "commit": {"type": "commit", "hash": "<the default branch'"'"'s head>"},
       "selector": {"type": "custom", "pattern": "ironbee-code-review"}}}'
```

In the repository's **Pipelines**, that run must succeed; its log says what is wrong when it does not. A start on a
branch (**Run pipeline** on a branch) is no probe: on a pull request's source branch it fails on purpose, and on any
other branch it ends with nothing done.

## On a pull request

| What happens | What the reviewer does |
|---|---|
| A pull request is opened, pushed or marked ready | reviews it: a first round reads the whole change, a later round what changed since the last |
| It is edited (title, description, reviewers) | reviews nothing new; answers what waits in the conversation |
| Someone who counts replies in one of the reviewer's threads | answers a question, when the team's `answerQuestions` setting is on. Who counts: the pull request's author, and people with the write or admin permission on the repository |
| Someone with the write or admin permission addresses the reviewer in the conversation | obeys a command, or answers a question |

People address the reviewer as `@ironbee-ai`, which is text the reviewer matches, the only name it answers to and the
name its own texts use; a mention of `Bitbucket Pipelines` is no name of its ([Identity](identity.md)). The commands:

| Command | What it does |
|---|---|
| `@ironbee-ai review` | reviews what was pushed since the last round. With nothing pushed, it reads nothing again and writes the status again from the pull request's texts |
| `@ironbee-ai full review` | reads the whole pull request again |
| `@ironbee-ai pause` | pauses automatic reviews of the pull request: a review a push starts stops as paused |
| `@ironbee-ai resume` | resumes them |
| `@ironbee-ai retract` | takes back every comment of the reviewer's on the pull request; the status becomes a `neutral` |

A comment of the reviewer's own, an app user's comment, and anything on a pull request from a fork start nothing. A
command from someone who may not write still starts a run through the trigger app, which ends before any call to
IronBee. A comment on a merged or declined pull request starts nothing. When the team's `summary` setting is on, the
summary is a comment of the reviewer's, never the description.

A round is published as Bitbucket allows: a comment for each finding, then the review's body, so its comments appear
one by one. A run killed half-way leaves comments that the next run removes before its own round
([What differs](differences.md)).
