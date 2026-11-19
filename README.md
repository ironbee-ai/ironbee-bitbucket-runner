# IronBee code review: the self-hosted runner for Bitbucket

This repository holds what IronBee's code review needs on Bitbucket Cloud to run on your own compute, with your own
model: **the block** your repository's `bitbucket-pipelines.yml` takes (one custom pipeline and the two triggers that
start it), **the trigger app's source** (a small Forge app of your own that starts the pipeline on a comment), and the
guide. A step in your repository's own Pipelines runs IronBee's reviewer, from a container image IronBee ships, on
your pull requests: first reviews and follow-up rounds after each push, answers to questions on its threads, and
commands addressed to it in the conversation. It writes its review on the pull request and a build status named
`Code Review Result` on the head commit, which Bitbucket's merge checks count.

- **Your code stays with you.** The repository is cloned and read inside your step. Model calls go from your step to
  your own model: your Anthropic, Amazon Bedrock or OpenAI account, or a model you host behind an OpenAI-compatible
  server.
- **Your settings and rules stay in the IronBee console**, as for IronBee's cloud product. Each run asks IronBee for
  them, and for the licence, when it starts.
- **Nothing of IronBee's runs in your workspace but the image.** The block is text in your own file; the trigger app is
  registered in your own Atlassian developer account, deployed by you and installed on your workspace. IronBee holds no
  token of yours and no app of its own there.
- **This release supports bitbucket.org.** Pull requests from forks are not reviewed: Bitbucket runs no pipeline for
  them.

[What reaches IronBee](docs/what-reaches-ironbee.md) prints every body IronBee receives.

## Quick start

You need, from IronBee: the self-hosted runner enabled on your account, your account's API key, and a registry token
for the image. From your side: an admin of the repositories to review, a key for your model and, for comments, a
workspace admin with Node.js 22 and Atlassian's Forge CLI.

IronBee's CLI sets a repository up for you, from your machine and with your own Atlassian API token:

```sh
npm install -g @ironbee-ai/cli
export BITBUCKET_TOKEN IRONBEE_API_KEY IRONBEE_REGISTRY_TOKEN IRONBEE_MODEL_KEY FORGE_EMAIL FORGE_API_TOKEN
ironbee runner setup --host bitbucket --repos acme/shop,acme/payments --model-provider anthropic \
  --developer-space <your developer space's id>
```

It registers the repositories with IronBee, turns Pipelines on where it is off, writes the variables, adds the block to
each repository's `bitbucket-pipelines.yml` (by a pull request where the file exists), sets up the trigger app once for
the workspace, and checks the whole with a probe. `ironbee runner add <workspace/repository>` serves one more
repository; `ironbee runner check` says what is missing or wrong, `--fix` repairs it, and `--probe` runs the probe.
[Setup](docs/setup.md) explains each step, and how to take the same steps by hand.

## The block

What a release puts into your `bitbucket-pipelines.yml`, beside whatever pipelines it holds
([`templates/bitbucket-pipelines.yml`](templates/bitbucket-pipelines.yml) at the release's tag):

```yaml
pipelines:
  custom:
    ironbee-code-review:                          # IronBee's code review, release 1.0.0
      - step:
          name: IronBee Code Review
          image:
            name: docker.io/ironbeeai/ironbee-code-review-runner@sha256:<the release's image>
            username: ironbeeai
            password: $IRONBEE_REGISTRY_TOKEN
          # runs-on: [self.hosted, linux]         # your own runner, when the model is inside your network
          max-time: 120
          concurrency-group: ironbee-code-review-${{BITBUCKET_PR_ID}}
          clone:
            enabled: false
          auth:
            system:
              scopes:
                - read:pullrequest:bitbucket
                - write:pullrequest:bitbucket
                - read:repository:bitbucket
                - read:git:bitbucket
          script:
            - ironbee-runner

triggers:
  pullrequest-created:
    - condition: glob(BITBUCKET_BRANCH, "**")
      pipelines:
        - ironbee-code-review
  pullrequest-updated:
    - condition: glob(BITBUCKET_BRANCH, "**")
      pipelines:
        - ironbee-code-review
```

- The step's image is named by digest: what runs is what the release tested, whatever becomes of a tag.
- The step clones nothing: the reviewer makes its own clone with the step's own token, `BITBUCKET_OAUTH_TOKEN`, which
  Bitbucket gives the step with the four scopes listed and nothing more ([Identity](docs/identity.md)).
- One run of a pull request at a time, by the concurrency group: a second waits its turn. A started run is never
  cancelled.
- The triggers add a pipeline of their own and replace none: your own `pull-requests:` pipelines are untouched.

## Variables

A step takes no input but its environment, so everything else is a Pipelines variable, the repository's by default:

| Variable | For | Secured |
|---|---|---|
| `IRONBEE_API_KEY` | IronBee's API | yes |
| `IRONBEE_REGISTRY_TOKEN` | the image's registry, read by Pipelines for the step's `image:` | yes |
| `IRONBEE_MODEL_PROVIDER` | `anthropic`, `bedrock` or `openai` (required) | no |
| `IRONBEE_MODEL_KEY`, `IRONBEE_MODEL_HEADERS` | the model's key, and its endpoint's extra headers | yes |
| `IRONBEE_MODEL_URL`, `IRONBEE_MODEL_NAME`, `IRONBEE_MODEL_CA_CERTIFICATE`, `IRONBEE_MODEL_PREFIX`, `IRONBEE_MODEL_MAX_OUTPUT`, `AWS_REGION` | the model | no |
| `IRONBEE_JEV_KEY` | Jev with your own key | yes |
| `IRONBEE_KNOWLEDGE_REPOSITORY`, `IRONBEE_KNOWLEDGE_REF` | the rules repository | no |
| `IRONBEE_KNOWLEDGE_TOKEN` | a read-only repository access token for it | yes |
| `IRONBEE_IGNORE_PATHS`, `IRONBEE_TARGET_BRANCHES`, `IRONBEE_SKIP_TITLE_KEYWORDS` | a repository left without a project in IronBee | no |
| `IRONBEE_API_URL`, `IRONBEE_RUN_REPORTS` | IronBee's API address when it is not the default; whether a run reports what it reviewed | no |

A Pipelines variable holds no line break, so a value of more than one line (headers, certificates, a list) is given as
`base64:` followed by the value in base64; the runner decodes it before anything reads it
([Setup](docs/setup.md#3-the-variables)). The workspace variable `IRONBEE_TRIGGER_APP` records the trigger app; it is
no secret and the runner never reads it.

## What starts a run

| On the pull request | What starts it | What the run does |
|---|---|---|
| opened; a push to it; a draft marked ready | Bitbucket's trigger | reviews the head (a first round, then follow-ups), when the gates let it |
| edited (title, description, reviewers) | Bitbucket's trigger | reviews nothing new; deals with what waits in the conversation |
| a reply on one of the reviewer's threads | the trigger app | answers it |
| a comment that addresses `@ironbee-ai` | the trigger app | obeys the command, or answers the question |

Every run reads from the pull request's own texts what is due, and a run that finds nothing due ends before it calls
IronBee. Without the trigger app, a reply or a command waits for the pull request's next push or edit.

## Documentation

| Page | What it covers |
|---|---|
| [Setup](docs/setup.md) | `ironbee runner setup`, and the same steps by hand: Pipelines, the variables, the block, the registration, the trigger app |
| [Merge checks](docs/merge-checks.md) | the `Code Review Result` status, the pipeline's own status, Bitbucket's merge checks, and what the status means |
| [Where the step runs](docs/compute.md) | Atlassian's runners, your own Bitbucket runner, and the build minutes |
| [The trigger app](docs/trigger-app.md) | what it does, what it holds, whose it is, and what to keep in mind |
| [Identity](docs/identity.md) | the step's token, who the reviewer writes as, who may ask, and the rules repository's token |
| [What reaches IronBee](docs/what-reaches-ironbee.md) | the bodies sent, what is never sent, what stays with you |
| [What differs](docs/differences.md) | from IronBee's cloud product on Bitbucket, and from the GitHub runner |
| [Troubleshooting](docs/troubleshooting.md) | what you see when something goes wrong, and what to do |

The model's settings, the review file, a rules repository, Jev and the licence work as on IronBee's other self-hosted
runners: [IronBee's GitHub runner](https://github.com/ironbee-ai/ironbee-github-runner) documents them, with each of
its inputs a variable of the same name here (`model-provider` is `IRONBEE_MODEL_PROVIDER`).

## Versions

A release is a tag `v1.0.0` of this repository, never moved: its template names the image `1.0.0` by digest and its
comment names the release, and its `trigger-app/` is the app's source of that release. `release.json` at the tag says
the same for the CLI. `ironbee runner setup` writes the latest release in full, or the one `--version` names; a block
that is there keeps its release until `--update` moves it, and `ironbee runner check` says when a newer release exists.

- `v1` follows the newest 1.x release, and is what the CLI reads by default.
- **Pre-releases**, `v1.0.0-rc.<N>`, name the image `1.0.0-rc.<N>`: builds for IronBee's own tests before the release,
  marked as pre-releases on GitHub and not for production. `v0` follows the newest of every release and pre-release,
  for IronBee's own demos.
- Within a major version, nothing you set is renamed or removed: the variables, the pipeline's name, the concurrency
  group, the status's name and key, and the marker the trigger app reads stay as they are.

## This repository

| Path | What |
|---|---|
| `templates/bitbucket-pipelines.yml` | the block; a release stamps its image and its release's name |
| `trigger-app/` | the trigger app: `manifest.yml` (no app's id: the setup registers one), `package.json` and `package-lock.json` pinning `@forge/api`, `src/index.js`, and its tests |
| `release.json` | the release's name, its image by digest, and the files the CLI reads at the release's tag |
| `scripts/release.sh`, `scripts/lib.sh` | a release, step by step |
| `.github/workflows/release.yml` | a release, started by hand on `main` with the version, the pre-release's number and the image's digest |
| `.github/workflows/build.yml` | the checks below, on every pull request and on `main` |
| `tests/` | the release script over stubs, the block, `release.json`, the workflows and the trigger app's manifest |

A release stamps the image's digest and the release's name into the template and `release.json` by a commit on `main`,
tags it, moves `v0` and, for a release, `v<MAJOR>`, and makes the GitHub release; it is refused for a digest Docker Hub
does not hold under the release's name. The checks: `python -m pytest`, and in `trigger-app/`
`npm ci --ignore-scripts && npm test`.
