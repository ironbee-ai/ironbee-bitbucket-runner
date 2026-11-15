# The trigger app

Bitbucket starts no pipeline on a comment, and a webhook cannot start one. What can turn a comment into a run with no
server of anyone's is a Forge app: Atlassian runs its function when a comment is made, and the function may call
Bitbucket's API. The trigger app is such an app, **of your own**: `ironbee runner setup` registers it in your
Atlassian developer space from this repository's source at the release it sets up, deploys it and installs it on your
workspace ([Setup](setup.md#the-trigger-app-step)). One app serves every repository of the workspace.

A workspace without it is reviewed all the same: every pull request's event starts a run, and each run deals with what
waits in the conversation. A reply or a command then waits for the pull request's next push or edit; saving the pull
request's description is such an edit.

## What it is

[`trigger-app/`](../trigger-app) at the release's tag: its `manifest.yml`, with no app's id (the setup registers
one), its `package.json` and `package-lock.json`, which pin its one dependency, `@forge/api`, and its one function,
`src/index.js`, some two hundred lines to be read.

- **One function**, on `avi:bitbucket:created:pullrequest-comment`.
- **Three scopes:** `read:pullrequest:bitbucket`, `read:pipeline:bitbucket` and `write:pipeline:bitbucket`. No
  repository or git scope: its own token reads no file of your repositories. A pipeline it starts can, which is the
  power of whoever can deploy to it ([below](#whose-power-it-is)).
- **Nothing outside Atlassian:** no remote, no address it may fetch, no storage.

## What it does

For each comment made on a pull request of the workspace:

1. **A person's comment only.** An app user's comment (the reviewer's own, written as `Bitbucket Pipelines`, among
   them) ends it before any read, so the app never answers the runner.
2. **The comment is read**, and, for a reply, the comments above it up to its thread's first, by their parent links,
   ten at the most. A reply deeper than that is taken all the same: the run reads the thread whole and tells whether it
   is the reviewer's.
3. **Is it for the reviewer?** When the comment addresses `@ironbee-ai` by the reviewer's own rule (its mention, read
   over the person's own words: quoted lines and fenced code left out), or its thread's first comment is the
   reviewer's (an app user's, carrying the reviewer's hidden marker). Where it cannot read a comment exactly as the
   reviewer does, it keeps more in, never less: it may start a run the reviewer then finds nothing in, and never misses
   one the reviewer would answer.
4. **The pull request is read:** it must be open, and its source must be the repository itself (a fork's pull request
   runs no pipeline of the repository's).
5. **The start:** `POST …/pipelines/` with the pull request as its target, its source and destination branches, its
   head and the destination's commit as the pull request gives them, and the custom pipeline `ironbee-code-review`, as
   Bitbucket's own trigger would. It hands the run nothing: the run finds the comment in the conversation. A start
   Bitbucket refuses (a repository whose file has no such pipeline, for one) is logged and dropped.

It leaves to the run whether the comment's writer may ask: the read of a person's permission needs a repository scope
the app does not hold. So a comment from someone who may not command still starts a run, which ends before any call to
IronBee.

**Its log** holds ids (the workspace's, the repository's, the pull request's and the comment's) and outcomes
(`started`, `not for us`, `start refused` with Bitbucket's status and its error's code…), never a comment's text, a
title or a branch's name. It is the app's developer's: `forge logs -e production`, run where the app's `manifest.yml` with its id is, signed
in as one of them.

**Its cost.** A delivery takes seconds as a rule, and may take up to three minutes; each comment that is for the
reviewer is then one run. A comment that is not for the reviewer costs one invocation of the function and no build
minute. Forge bills an app's use to its developer, here you, past a free allowance a trigger does not come near.

## Whose it is

Yours. You are its developer: its logs are yours, a new version is yours to deploy (`ironbee runner setup --update`, at
a later release), and IronBee holds no token of it, cannot change its code and sees nothing of what it does.

The workspace's variable `IRONBEE_TRIGGER_APP` records it: `{"app":"ari:cloud:ecosystem::app/<uuid>","release":"1.0.0"}`,
no secret. The runner never reads it; the setup and `ironbee runner check` do, to find the app again and to compare its
release with the latest.

## Whose power it is

`write:pipeline` is the power to start any pipeline in any repository of the workspace, of any definition (one handed
in with the call included), its steps given that repository's variables. Such a step clones its repository: so whoever
can make the app's function start one can run a step that reads any repository's code and variables, though the app's
own token reads no file. It lies with whoever can deploy to the app:
the Atlassian account that registered it, and every account its developer space lets deploy, whether or not that
person can push to any repository, and still after they left the workspace, since the app is the account's and not the
workspace's. That is the power of an administrator of every pipeline secret and every repository's code of the
workspace. IronBee holds none of it.

So, before it registers anything, the setup says this and asks you to go on, and asks four things of you:

1. **Register the app in a developer space your company keeps for it, with more than one administrator,** so that the
   app need not leave with a person. Should the member who registered it leave, have the app's ownership handed over by
   Atlassian's own procedure before they go; Atlassian's developer console shows who owns an app.
2. **Keep that space to the people who administer the workspace.** The person who runs the setup is one of them, and an
   admin of the workspace, which Atlassian requires of whoever installs an app.
3. **Revoke the Atlassian API token of the setup** (`FORGE_API_TOKEN`) when the command has ended.
4. **Deploy to Forge's production environment alone,** where no developer's machine stands in for the function.

A workspace that will not carry this goes without the app. What you trust beyond that is the source you deploy, which
is public and short.

## Not the setup's

- **Sharing the app** with another workspace (a form in Atlassian's developer console): an app not shared can be
  installed by its own developers alone, which is all the setup needs.
- **Removing it:** `forge uninstall -e production -p Bitbucket -s bitbucket.org/<workspace>`, then the workspace's
  variable `IRONBEE_TRIGGER_APP`. Comments then wait for the pull request's next event.
