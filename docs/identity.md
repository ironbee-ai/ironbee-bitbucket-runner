# Identity

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
