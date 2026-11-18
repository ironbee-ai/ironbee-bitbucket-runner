# Merge checks

Two build statuses of the review stand on a pull request's head commit: the reviewer's own, `Code Review Result`, and
the one Bitbucket writes for the review pipeline itself. Bitbucket's merge checks count both, as they count every build
status on the head.

## The `Code Review Result` status

One build status per head commit, written by the runner alone, with the step's token:

| | |
|---|---|
| name | `Code Review Result` |
| key | `ironbee-` and the first 32 hexadecimal characters of the name's SHA-1 (Bitbucket takes forty characters) |
| `refname` | the pull request's source branch |
| state | `FAILED` for a blocking review; `SUCCESSFUL` for a passing review, and for a `neutral` |
| description | the findings' counts, or a `neutral`'s reason in one sentence |
| link | the review of the reviewer's on that head (its comment on the pull request); a `neutral`'s is the pull request's page with `#ironbee-neutral`, a retract's with `#ironbee-retracted`, which is how a later run tells them from a passing review |

A `neutral` is a review that did not run (a draft, a gate, the licence, a variable set wrong): it passes, and its
sentence says why.

### How it concludes

| What happened | The status |
|---|---|
| A review read the head | its conclusion: `FAILED` when findings nobody who counts turned down hold the merge, `SUCCESSFUL` otherwise |
| A run reviewed nothing (a gate, a pause, a refusal by IronBee, a variable missing) | a `neutral`, only on a head with no status of the reviewer's and no review of its |
| `@ironbee-ai retract` | a `neutral` on the head it is obeyed on, whatever that head held: the retract's own record, which a later run reads |
| An answer, or a command that asks for no review | as it was |
| `@ironbee-ai review` on a head already read | written again from the pull request's texts, nothing read again |

A head that gets `FAILED` holds a review of the reviewer's: where nothing new was read there, a short review naming that
head is posted first. A reply that turns a finding down ("won't fix") and a thread someone resolves are recorded by the
next review that reads the pull request again (a push, or `@ironbee-ai full review`).

## The pipeline's own status

Bitbucket itself writes a status for each pipeline that runs on a commit: for the review pipeline, key
`custom:ironbee-code-review`, named `Pipeline - custom: ironbee-code-review`, on the commit the pipeline was started
for. It is `INPROGRESS` while a run is under way or waits its turn, then the run's result; a later run on the same commit
writes over it. That is why a run works on its pipeline's own commit and on no other: both statuses of a head are always
that head's. A run whose head was pushed over ends at once; the newer head's own run reviews it.

| What happened | The pipeline's own status | `Code Review Result` |
|---|---|---|
| a run is under way, or waits in the pull request's queue | `INPROGRESS`: where builds block, the merge waits for it | as the last run left it |
| the run ended by its own doing: nothing was due; a review concluded; a conclusion written from the texts; a gate; a refusal by IronBee or IronBee unreachable, on a head owed no conclusion; a variable missing or wrong, on such a head; a failure before its review was posted, its first reads of Bitbucket done; a comment answered or not | `SUCCESSFUL` (the step exits 0) | by the rule above |
| the runner failed after its review was posted, or while it concluded; or a run found a head owed a conclusion and could not write it | `FAILED` (the step exits 1) | as it was: the head holds a review of the reviewer's and no conclusion |
| the run was killed or timed out, or its image could not be pulled | `FAILED`, `STOPPED` or an error, as Bitbucket has it | as it was |
| a start with no pull request on a pull request's source branch (**Run pipeline** on that branch) | `FAILED` (the step exits 1), its log saying how a pull request's run is started | as it was |
| the run's first reads of Bitbucket failed (Bitbucket down, a second 429) before it knew whether its head is owed a conclusion | `FAILED` (the step exits 1) until the next run on that head reads it through: a pass there could lift a dead run's hold | as it was |

- **The step exits 0 for everything a `neutral` or nothing answers,** so a licence problem, a gate, an unreachable
  IronBee, a variable set wrong or a comment that could not be answered never shows a failed build: only a review holds
  a merge. The pipeline's log, and a `neutral`'s sentence, say what happened. It exits 1 only where the table says so, each
  a case where a pass would say more than is true, Bitbucket's own reads failing before the run knows what its head is
  owed among them.
- **No later run passes a head whose review was never concluded by just ending.** Any run that comes next on it (an
  edit's, a comment's, a re-run) finds a review of the reviewer's with no conclusion and writes the conclusion from the
  texts before anything else. So the failed build a dead run left is replaced by a pass only together with the review's
  own conclusion, `FAILED` where its findings block. A run that died before it posted anything left a head with no
  review of the reviewer's: the next run on it reviews it.
- **A run stopped by hand** leaves `STOPPED`, which the merge check is reported not to count. Stopped between its review
  and its conclusion, it leaves posted findings with neither a failed build nor a conclusion; the next run on that head
  writes the conclusion, and until one comes the merge check sees nothing of the reviewer's there.
- **What the runner cannot tell holds.** An image that cannot be pulled (a wrong registry token, the registry down)
  fails the pipeline before the runner starts, on every pull request, until it is put right: where builds block, that
  holds the merges. `ironbee runner check --probe` finds it on the day of the setup.
- **While a comment's run is under way** the head shows a build in progress, for as long as the answer takes; where
  builds block, a merge waits that long.

## Making merges wait for it

Bitbucket's merge checks are set per branch, in the repository's branch restrictions (**Repository settings** >
**Branch restrictions**, a restriction's merge settings):

- **"Minimum number of successful builds for the last commit with no failed builds and no in progress builds"**: a
  merge waits for every build status on the head to be neither failed nor in progress. A blocking review is a failed
  build; a review under way is a build in progress; a run that died is a failed build until the pipeline runs again on
  that head. A head with no build at all waits too, for want of a successful one.
- **"Prevent a merge with unresolved merge checks"**, on Premium alone: without it, the checks warn and the merge button
  works.

**The second holds every merge check of the branch, not the builds check alone.** With "Prevent a merge with
unresolved merge checks" on, each merge check the branch has holds a merge: a number of approvals, of default
reviewers' or of a review group's approvals, no changes requested, every task completed, every comment resolved, at
most a number of commits behind, every dependency merged. A check that only warned becomes a condition of every merge
into the branch: a pull request whose review passed is still refused while it lacks an approval the branch asks for.

**"No changes are requested" goes with "Reset requested changes when the source branch is modified".** Under the
enforcement a request for changes holds a merge until it is taken back, and a later review of the reviewer's does not
take back one it made. With the reset on, set in the same place, the next push to the pull request's source branch
clears it.

### With the CLI

`ironbee runner setup` does not set them. `ironbee host merge-check` does, from your machine, with your
`BITBUCKET_TOKEN` ([Sign in](setup.md#sign-in)), of whose scopes it needs `read:repository:bitbucket` and
`admin:repository:bitbucket`, as a repository admin:

```sh
ironbee host merge-check acme/shop
ironbee host merge-check acme/shop --branch release
```

The repository is the one named, else the directory's git remote; the branch is the repository's default branch unless
`--branch` names one. The command reads the branch's restrictions and adds, where absent, each after asking: the merge
check that asks for at least 1 successful build on a pull request's last commit, with none failed or in progress; then
"Prevent a merge with unresolved merge checks". Before it asks for the second, it names every other merge check of the
branch, each of which then holds a merge too, says that it does not read a custom merge check an app defines, which is
set up elsewhere, and, where "No changes are requested" is on without its reset, what that pair means. A restriction
that is there is left as it is, whatever its count, and nothing is removed: a second run changes nothing. `-y`
(`--yes`) makes each change without asking; with no terminal and no `-y`, each is left undone and said. It ends with
what is on the branch now. It reads no plan, so its words say both: on a Premium workspace the checks hold a merge, on
Free and Standard they only warn.

`ironbee runner check` reads the same restrictions of the default branch, as information: whether its merge checks ask
for a successful build and are enforced, what that does on each plan, and, where the builds check or the enforcement is
absent, that `ironbee host merge-check` adds it. `ironbee runner setup` and `add` end with a note that names it.

A restriction is removed where it was set: **Repository settings** > **Branch restrictions**.

## What the status is worth

**What the status says, in IronBee's cloud product and here.** It reflects the findings that nobody who counts has
turned down. The pull request's author, and anyone else who counts, can close a finding with a reply; someone who may
write to the repository can resolve a thread, `retract`, or `pause` and then push. The status is a team's own
discipline made visible, not a control over its members: a team that must hold merges against its own developers
requires a human approval beside it.

What Bitbucket adds:

- **It holds a merge only on Premium,** with "Minimum number of successful builds" set and "Prevent a merge with
  unresolved merge checks" on. On Free and Standard the same check warns, and the merge button works.
- **The check names no status, so it cannot require that a review ran.** It asks for a number of successful builds and
  for none failed or in progress, among all of the head's statuses. A blocking review holds the merge (a failed build),
  a review under way holds it (a build in progress), a dead run holds it (a failed build). But a head no run was started
  for holds nothing of the reviewer's (a branch without the block; an event Bitbucket started no pipeline for), and no
  number closes that: every run of the review pipeline adds a successful build, a gated one and an edit's too.
- **Forgeable, as on GitHub.** Anyone who can push a branch can change the file on it, read the variables the step is
  given, and write a status or a comment Bitbucket does not tell from the reviewer's ([Identity](identity.md)). That is
  Bitbucket's rule for every secured variable and every status a pipeline writes, not this feature's.
