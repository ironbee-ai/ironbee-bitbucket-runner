# Identity, and what a pushed branch can do

The reviewer reads the repository and writes its comments and the `Code Review Result` status with one credential: the
token Bitbucket gives each step, `BITBUCKET_OAUTH_TOKEN`. There is nothing to create, and IronBee holds no credential
of yours.

| | |
|---|---|
| The token | the step's own; limited to the repository the pipeline runs in and to the scopes the step lists; it ends with the step (two and a half hours at the most, above the step's two hours) |
| Its scopes | `read:pullrequest:bitbucket`, `write:pullrequest:bitbucket`, `read:repository:bitbucket` (which also writes build statuses and reads a person's permission on the repository), `read:git:bitbucket` (the reviewer's clone; the step itself clones nothing) |
| Comments and the status appear as | `Bitbucket Pipelines`, Bitbucket's app user |
| People address it as | `@ironbee-ai`: text the reviewer matches, the only name it answers to, and the name its own texts use; a mention of the `Bitbucket Pipelines` user is no name of its |
| Its own texts | told by the reviewer's hidden marker beside the author; it reads only the status of its own key |

The account the token writes as is read from the token itself (Bitbucket gives a step's token no `GET /user`). A runner
of yours needs version 6.1.0 or later for the token ([Where the step runs](compute.md)).

## Who may ask

The reviewer reads a commenter's effective permission on the repository with the step's token, once per person and run:

- **A command** (`@ironbee-ai review`, `pause`, `retract`…) is obeyed from someone with the **write** or **admin**
  permission.
- **A reply on one of its threads** counts from the pull request's author, or from someone with the write or admin
  permission.
- **An app user's comment** is a bot's, and counts for nothing.

## The rules repository

The step's token reaches its own repository alone: another repository of the same workspace answers it as if there
were none. A rules repository therefore needs a token of its own: a **repository access token** of the rules repository
with read access (**Repository settings** > **Access tokens**, on every plan), set as the secured variable
`IRONBEE_KNOWLEDGE_TOKEN`. When the rules repository cannot be read, the review goes on and says so.

## What a pushed branch can do

A pull request's events run **the `bitbucket-pipelines.yml` its source branch brings**. So anyone who can push a branch
to the repository can, on that branch:

- change the block, or any step, and run it;
- read every variable a step is given, the secured ones included, by printing it from a step of their own;
- write a build status named `Code Review Result`, or comments carrying the reviewer's marker and state, as
  `Bitbucket Pipelines`, which Bitbucket does not tell from the reviewer's.

Atlassian says the same of every secured variable: it is Bitbucket's rule, not this feature's, and the base of
[what the status is worth](merge-checks.md#what-the-status-is-worth). A workspace's variables widen it to everyone who
can push to any repository of the workspace, which is why the repository's variables are the default. Below Premium,
Bitbucket has no variable only a protected branch's pipelines read.

What a step writes, other pipelines' steps write as too: `Bitbucket Pipelines` is the one identity of every step
token. The reviewer's state lives in its comments as hidden lines, unsigned, as on every host: anyone who can post as
that identity can change it.

The trigger app holds a power of its own, its developers' rather than a pushing person's
([The trigger app](trigger-app.md#whose-power-it-is)).
