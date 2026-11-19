# What differs

## From IronBee's cloud product on Bitbucket

| | IronBee's cloud product | The self-hosted runner |
|---|---|---|
| Where the code is read | IronBee's cloud | your repository's own Pipelines |
| Model | IronBee's | yours |
| Comments' and the status's author | IronBee's app | `Bitbucket Pipelines`, the identity of every step's token ([Identity](identity.md)) |
| Starts on | IronBee's app's events | Bitbucket's own triggers for a pull request's events, and your own [trigger app](trigger-app.md) for comments |
| A reply or a command | seconds to start | answered by a run your trigger app starts: a delivery of seconds as a rule and up to three minutes, then a queue's wait and an image pull; without the app, by the pull request's next run. One from someone who may not ask still costs a run, which ends before any call to IronBee. One on a merged or declined pull request starts nothing |
| An edit of the pull request | reviews nothing | starts a run: on a head whose review is concluded it finds nothing due (an image pull and a few reads, no call to IronBee); on a head a gate held (a draft, by default) it asks the gate again |
| A round's comments | appear one by one | the same; a run killed half-way leaves comments that the next run removes, except one someone replied to, which the next round adopts |
| The status | `IronBee review` | `Code Review Result`, by the same rule ([Merge checks](merge-checks.md)) |
| The head a run works on | the newest | the commit its pipeline was started for: a run whose head was pushed over ends, and the newer head's own run reviews it |
| Follow-up rounds, fixed and dropped tracking, the summary (a comment, never the description), suggested fixes, answers, commands, retract | yes | yes |
| An image in what the model writes | shown | left as its text and its address ([What reaches IronBee](what-reaches-ironbee.md#untrusted-input)) |
| Release merges | read whole | read whole |
| Labels | none on Bitbucket: `skipLabels` has no effect | the same |
| Secrets | none of yours in the repository | secured Pipelines variables of the repository (or of the workspace) |
| Compute | IronBee's | each run is build minutes of your workspace's plan; your own runner's are not counted ([Where the step runs](compute.md)) |
| Per-repository settings | the console | the console, on the repository's IronBee project; variables only for a repository left without one |
| Rules and memories you keep | the repository's `.ironbee/` files | those, and a rules repository for all your repositories |
| Learning from reactions across pull requests | yes | no: a self-hosted run honours what people said on the pull request it reviews, and cannot remember it for the next |
| Console: pull requests, findings, summaries | yes | a list of each repository's pull requests and their runs, from counts; no finding or summary text |
| The licence | credits | an end date and a developer limit |
| Forks | not reviewed | not reviewed: Bitbucket runs no pipeline for them, and nothing appears on their pull requests |

A repository connected to IronBee's cloud product with code review on cannot also be served by a runner: its
registration and its runs are refused (`REPOSITORY_REVIEWED_BY_CLOUD`), so the cloud's reviewer and yours never answer
the same pull request. Turn its code review off in the console first.

## From IronBee's GitHub runner

| | GitHub runner | Bitbucket runner |
|---|---|---|
| What a reviewed repository changes | a workflow file and its secrets | a block in `bitbucket-pipelines.yml`, and its variables |
| How a comment starts a run | the workflow's comment events | your own trigger app, a Forge app; without it, the pull request's next event |
| The decide step | a step before the image is pulled | none: the trigger app starts a run only for a comment that is for the reviewer, and a run that finds nothing due ends before any call to IronBee |
| The repository credential | the job's own token, or your GitHub App | the step's own token; no app of your own for writing |
| Who it writes as | `github-actions[bot]` | `Bitbucket Pipelines` |
| The merge gate | a check run, `Code Review Result`, required by name | a build status, `Code Review Result`, counted with every other by Bitbucket's merge checks, which hold a merge on Premium alone ([Merge checks](merge-checks.md)) |
| A run that dies | the required check stays missing | the review pipeline's own status is a failed build; the next run on that head concludes the review |
| A run that fails | the workflow's fallback writes a `neutral` check | no fallback: the step exits 0 for whatever a `neutral` or nothing answers, and 1 only where a pass would say more than is true (a review posted and not concluded, a conclusion owed and not written, a start on a pull request's source branch, Bitbucket's reads failing before the run knows whether its head is owed a conclusion), a failed build until the next run on that head ([Merge checks](merge-checks.md#the-pipelines-own-status)) |
| A run whose head was pushed over | reviews the newest head | ends at once: the newer head has its own run |
| The summary | in the description | a comment |
| A round's comments | one review, published at once | one comment each, then the review's body |
| Who may command | write access, by GitHub's collaborator permission | write or admin permission on the repository, read with the step's token |
| Setup | `ironbee runner setup --host github`, or a file and its secrets by hand | `ironbee runner setup --host bitbucket`, or the same objects by hand ([Setup](setup.md)) |

The runner itself is the same: one image, one version for every host, the same profiles, models, review file, rules
repository, licence and compatibility rules.

## What running on Bitbucket changes

| Bitbucket's rule | What it means here |
|---|---|
| No pipeline starts on a comment, and a webhook cannot start one. | The trigger app, a Forge app of your own, starts the pipeline for a comment that is for the reviewer ([The trigger app](trigger-app.md)). |
| A pull request's events run the file its source branch brings. | A branch without the block starts nothing. |
| No pipeline starts for a fork's pull request. | Not reviewed; nothing of the reviewer's appears on it. |
| A thread a person resolves raises no event a pipeline starts on. | Recorded by the next review that reads the pull request again. |
| The step's token reads its own repository alone. | A rules repository needs a token of its own. |
| No merge check names a status. | The status cannot require that a review ran ([Merge checks](merge-checks.md#what-the-status-means)). |
| A build status cannot be deleted. | A retract writes a `neutral` over a review's conclusion; nothing is taken away. |
| A pull request holds at most 200 comments. | A round that cannot post its comments is published as its body alone ([Troubleshooting](troubleshooting.md)). |
| Bitbucket has no draft review another call could publish. | A round's comments appear one by one; the next run removes what a killed run left. |
| Raw HTML is shown as text, and a line Bitbucket hides is hidden only when it is the whole line. | The reviewer's state is a hidden line of its own under its marker in its comments, unseen on the pull request and kept in the comment's source. |
