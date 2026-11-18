# Where the step runs

On Atlassian's runners, or on a Bitbucket runner of yours.

- A model reachable from the internet, such as your Anthropic, Bedrock or OpenAI account, works from Atlassian's
  runners.
- **A model inside your network needs a runner of yours there**, named by the step's `runs-on`. It connects outward
  only.
- **A workspace on Premium that limits its private content to listed addresses**, or that requires two-step
  verification, works from Atlassian's runners: neither reaches the step's own token, so the run reads the pull
  request, clones it, comments and sets its status as anywhere else. The list does reach a repository access token,
  which is what reads a [rules repository](setup.md#3-the-variables) (`IRONBEE_KNOWLEDGE_TOKEN`): from Atlassian's runners, whose
  addresses no list holds, that read is refused, and the review goes on without your rules and says so in the log. To
  have the rules read, run the step on a runner of yours (`runs-on`) at an address the list holds.

## The step

| | |
|---|---|
| image | IronBee's runner image, named by digest in the block, built for `linux/amd64` and `linux/arm64`; pulled by Pipelines with `IRONBEE_REGISTRY_TOKEN` |
| what runs | `ironbee-runner`, in the step's shell: the image's entry point is not used, and the command makes a home and a cache the run's user can write before it starts the runner |
| how long | at most two hours (`max-time: 120`); every part of a run has its own timeout inside it |
| at once | one step of a pull request at a time (`concurrency-group`); the next waits its turn, and a waiting run holds no build minutes |
| size | the step's default size. A review of the largest pull request the size bounds let through is expected to fit; a step that runs out of memory takes `size: 2x`, at twice the minutes |

Bitbucket runs at most ten steps at once on the Free plan, and six hundred on a paid one, across all of the
workspace's pipelines.

## What a runner of yours needs

- **A Linux Docker runner** (the step runs in the image), on `amd64` or `arm64`. Bitbucket labels an `amd64` one
  `self.hosted` and `linux`, an `arm64` one `self.hosted` and `linux.arm64`. A Windows, macOS or Linux shell runner
  cannot run it.
- **Version 6.1.0 or later.** The step's token, `BITBUCKET_OAUTH_TOKEN`, needs it; an older runner fails the pipeline
  before the runner starts.
- **Network:** the step connects to bitbucket.org, your model's endpoint and IronBee's API (`api.service.ironbee.ai`, or
  the address in `IRONBEE_API_URL`), and nothing else; with your Jev key, also Jev's endpoint. The runner pulls the
  image from Docker Hub (`docker.io`).

### Making the step run on it

1. Register a Linux Docker runner for the workspace or the repository (**Workspace settings** or **Repository
   settings** > **Pipelines** > **Runners**), with any labels of your own beside Bitbucket's, and start it as
   Atlassian's page says.
2. Name its labels in the step's `runs-on`, in place of the block's commented line. An `amd64` runner:

   ```yaml
         - step:
             name: IronBee Code Review
             runs-on:
               - self.hosted
               - linux
   ```

   An `arm64` runner:

   ```yaml
         - step:
             name: IronBee Code Review
             runs-on:
               - self.hosted
               - linux.arm64
   ```

   With the setup command: `--runs-on self.hosted,linux` for an `amd64` runner, `--runs-on self.hosted,linux.arm64` for
   an `arm64` one, with any label of your own added. `--update` keeps a step's `runs-on` when it moves the block to
   another release.

Labels no runner has leave the pipeline waiting: the setup's probe finds that.

## Build minutes

On Atlassian's runners **every run is build minutes of the workspace's plan**: 50 a month on Free, 2,500 on Standard,
3,500 on Premium. A runner of yours spends none of them: Bitbucket does not count its minutes, and up to a hundred
runners are free on every plan.

- **Every event of a pull request starts a run**: an open, a push, a draft marked ready, an edit of the title, the
  description or the reviewers, and each comment that is for the reviewer (through the trigger app). A run that finds
  nothing due ends before it calls IronBee, but it has pulled the image and read the pull request: a short run, and a
  run all the same.
- **A review** takes minutes as a rule.
- **Your own pipelines** spend minutes on their own. To keep a repository off Atlassian's minutes altogether, your own
  steps need `runs-on` too: the review step's `runs-on` moves only the review.

**A workspace that has spent its minutes starts no pipeline**: no review and no status until the plan's month turns or
the runs move to a runner of yours.
