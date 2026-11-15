#!/usr/bin/env bash
# A release of this repository, one step at a time: scripts/release.sh STEP, run from the repository's root by the
# release workflow (.github/workflows/release.yml), or by hand on a machine signed in to Docker Hub and to GitHub. Every
# step reads the release's input from its environment and checks it by its form first; nothing is ever evaluated as
# code.
#
#   IRONBEE_VERSION        MAJOR.MINOR.PATCH
#   IRONBEE_RC             empty for a release; <N> for the pre-release MAJOR.MINOR.PATCH-rc.<N>
#   IRONBEE_IMAGE_DIGEST   sha256:<64 hex>: the runner image's index digest, as its publishing gave it
#
# The release's name is MAJOR.MINOR.PATCH or MAJOR.MINOR.PATCH-rc.<N>: the image's tag on Docker Hub, the name the
# template's comment and release.json's version carry, and the repository's tag v<name>.
#
#   plan             the release's tag new, or this very release's (a run again after its push); a release never below
#                    the newest one; no pre-release of a released version; the template and release.json stampable
#   digest           Docker Hub's tag of the release's name names IRONBEE_IMAGE_DIGEST (read signed in to Docker Hub)
#   stamp            the template and release.json given the image and the name, in the working tree, over whatever
#                    values they held
#   publish          Docker Hub's tag checked again as the digest step checks it, so that no run by hand stamps a digest
#                    nobody checked; then the stamp committed on main, tagged, the floating tags moved, all pushed at
#                    once; nothing when the tag is already this release's
#   github-release   the GitHub release, when it is missing (GH_TOKEN); a pre-release marked so
#
# Exit 0: done; 1: refused, or a call that failed; 2: the inputs, the repository or the machine.
set -euo pipefail
# shellcheck source=scripts/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

IMAGE=docker.io/ironbeeai/ironbee-code-review-runner
TEMPLATE=templates/bitbucket-pipelines.yml
RELEASE=release.json
TRIGGER_APP='["trigger-app/manifest.yml", "trigger-app/package.json", "trigger-app/package-lock.json", "trigger-app/src/index.js"]'

VERSION='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
RC='^[1-9][0-9]*$'
NAME_FORM='(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-rc\.[1-9][0-9]*)?'
RELEASE_TAG='^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
DIGEST='^sha256:[0-9a-f]{64}$'
ZEROS=sha256:$(printf '%064d' 0)
# The template's two stamped lines, each holding a release's value or, before the first release, its placeholder: the
# pipeline's line, whose comment names the release, and the step image's name.
NAME_LINE="^([[:space:]]*ironbee-code-review:[[:space:]]+# IronBee's code review, release )(__IRONBEE_RELEASE__|$NAME_FORM)\$"
IMAGE_LINE='^([[:space:]]*name:[[:space:]]+)(__IRONBEE_IMAGE__|docker\.io/ironbeeai/ironbee-code-review-runner@sha256:[0-9a-f]{64})$'

# bot ARGS...: git as github-actions[bot], the author, committer and tagger of what a release writes.
bot() {
  GIT_AUTHOR_NAME='github-actions[bot]' GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com' \
    GIT_COMMITTER_NAME='github-actions[bot]' GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com' git "$@"
}

# The input by its form, and what comes from it: name (the release's whole name), tag (v<name>) and floating (v<MAJOR>
# follows the releases of that major version; v0, the newest of every release and pre-release, moves with each).
inputs() {
  version=${IRONBEE_VERSION:-}
  rc=${IRONBEE_RC:-}
  [[ $version =~ $VERSION ]] || fail 2 "version is not MAJOR.MINOR.PATCH"
  major=${BASH_REMATCH[1]}
  if [ -n "$rc" ]; then
    [[ $rc =~ $RC ]] || fail 2 "rc is neither empty (a release) nor a whole number from 1 (a pre-release)"
    name=$version-rc.$rc
    floating=v0
  else
    [ "$major" != 0 ] || fail 2 "a release of major version 0: v0 is the tag of the newest release or pre-release"
    name=$version
    floating=v$major
  fi
  tag=v$name
}

# The image's index digest, given with the release: every step works by it, the digest step checks it against Docker Hub.
digest_read() {
  digest=${IRONBEE_IMAGE_DIGEST:-}
  [[ $digest =~ $DIGEST ]] || fail 2 "IRONBEE_IMAGE_DIGEST is not sha256:<64 hex>"
  [ "$digest" != "$ZEROS" ] || fail 2 "IRONBEE_IMAGE_DIGEST is the placeholder of all zeros"
  image=$IMAGE@$digest
}

# newer A B: whether version A is above version B, each MAJOR.MINOR.PATCH with no leading zero.
newer() {
  local a b i x y
  IFS=. read -r -a a <<< "$1"
  IFS=. read -r -a b <<< "$2"
  for i in 0 1 2; do
    x=${a[$i]}
    y=${b[$i]}
    if [ "${#x}" != "${#y}" ]; then
      [ "${#x}" -gt "${#y}" ]
      return
    fi
    if [ "$x" != "$y" ]; then
      [[ $x > $y ]]
      return
    fi
  done
  return 1
}

# later A B: whether release name A (MAJOR.MINOR.PATCH, or with -rc.<N>) comes after B: by version, then a release after
# its pre-releases, then the higher pre-release.
later() {
  local one=${1%%-*} two=${2%%-*} rc1 rc2
  if [ "$one" != "$two" ]; then
    newer "$one" "$two"
    return
  fi
  rc1=${1#"$one"}
  rc2=${2#"$two"}
  if [ -z "$rc1" ] || [ -z "$rc2" ]; then
    [ -z "$rc1" ] && [ -n "$rc2" ]
    return
  fi
  [ "${rc1#-rc.}" -gt "${rc2#-rc.}" ]
}

# moves_of: the floating tags this run moves, in words (moves), and the newest release name of all (keep) when it is
# later than this one: v0 follows the newest, so a release of an older line moves its own major version's tag alone, and
# the newest puts v0 back where it belongs wherever it was moved by hand.
moves_of() {
  local t newest=""
  while IFS= read -r t; do
    [[ ${t#v} =~ ^$NAME_FORM$ ]] || continue
    if [ -z "$newest" ] || later "${t#v}" "$newest"; then
      newest=${t#v}
    fi
  done < <(git tag -l 'v*')
  keep=""
  if [ -n "$newest" ] && later "$newest" "$name"; then
    keep=$newest
  fi
  if [ -n "$rc" ]; then moves=""; else moves=$floating; fi
  if [ -z "$keep" ]; then moves=${moves:+$moves and }v0; fi
}

# stays LATER: what becomes of v0 when the later release LATER keeps it, in words: it stays, or, where there is none
# yet, none is made; nothing when LATER is empty.
stays() {
  [ -n "$1" ] || return 0
  if git rev-parse -q --verify "refs/tags/v0" > /dev/null; then printf '; v0 stays, v%s being later' "$1"; else printf '; no v0 is made, v%s being later' "$1"; fi
}

# The newest release's version among the tags, or nothing.
newest_release() {
  local t newest=""
  while IFS= read -r t; do
    [[ $t =~ $RELEASE_TAG ]] || continue
    if [ -z "$newest" ] || newer "${t#v}" "$newest"; then
      newest=${t#v}
    fi
  done < <(git tag -l 'v*')
  printf '%s' "$newest"
}

# stamp_template FILE LABEL OUT: FILE with its pipeline's line naming the release and its step image's name line
# given this release's name and image, written to OUT. Sets was_name and was_image to what FILE named. LABEL is FILE's
# name in the messages.
stamp_template() {
  local file=$1 label=$2 out=$3 line names=0 images=0
  was_name=""
  was_image=""
  while IFS= read -r line || [ -n "$line" ]; do
    if [[ $line =~ $NAME_LINE ]]; then
      names=$((names + 1))
      was_name=${BASH_REMATCH[2]}
      line=${BASH_REMATCH[1]}$name
    elif [[ $line =~ $IMAGE_LINE ]]; then
      images=$((images + 1))
      was_image=${BASH_REMATCH[2]}
      line=${BASH_REMATCH[1]}$image
    fi
    printf '%s\n' "$line"
  done < "$file" > "$out"
  [ "$names" = 1 ] || fail 2 "$label: the pipeline's line naming the release is there $names times, not once"
  [ "$images" = 1 ] || fail 2 "$label: the step image's name line is there $images times, not once"
}

# stamp_json FILE LABEL OUT: release.json FILE given this release's name and image, written to OUT, its other members as
# they are. Sets was_version and was_json_image to what FILE named (empty for its placeholders, null).
stamp_json() {
  local file=$1 label=$2 out=$3
  jq -e --arg template "$TEMPLATE" --argjson app "$TRIGGER_APP" \
    'type == "object" and keys == ["image", "template", "triggerApp", "version"] and .template == $template and .triggerApp == $app
     and (.version == null or (.version | type) == "string") and (.image == null or (.image | type) == "string")' \
    "$file" > /dev/null 2>&1 || fail 2 "$label is not release.json's shape: version, image, template ($TEMPLATE) and triggerApp (the trigger app's four files)"
  was_version=$(jq -r '.version // ""' "$file")
  was_json_image=$(jq -r '.image // ""' "$file")
  jq --arg name "$name" --arg image "$image" '.version = $name | .image = $image' "$file" > "$out"
}

# The files a release names: the template, and the trigger app's, which the setup reads at the release's tag.
files_present() {
  local file
  [ -f "$TEMPLATE" ] || fail 2 "$TEMPLATE is missing"
  [ -f "$RELEASE" ] || fail 2 "$RELEASE is missing"
  while IFS= read -r file; do
    [ -f "$file" ] || fail 2 "$file is listed in $RELEASE and missing"
  done < <(jq -rn --argjson app "$TRIGGER_APP" '$app[]')
}

# pushed: whether the release's tag exists, its commit's template and release.json naming this image and this name: a
# run again after its push. A tag that names anything else is refused, since a tag is never moved.
pushed() {
  git rev-parse -q --verify "refs/tags/$tag" > /dev/null || return 1
  git show "refs/tags/$tag:$RELEASE" > "$IRONBEE_TMP/tagged.json" 2> /dev/null || fail 1 "$tag exists without $RELEASE: a tag is never moved"
  git show "refs/tags/$tag:$TEMPLATE" > "$IRONBEE_TMP/tagged.yml" 2> /dev/null || fail 1 "$tag exists without $TEMPLATE: a tag is never moved"
  stamp_json "$IRONBEE_TMP/tagged.json" "$tag:$RELEASE" "$IRONBEE_TMP/tagged.stamped.json"
  stamp_template "$IRONBEE_TMP/tagged.yml" "$tag:$TEMPLATE" "$IRONBEE_TMP/tagged.stamped.yml"
  if [ "$was_version" != "$name" ] || [ "$was_json_image" != "$image" ] || [ "$was_name" != "$name" ] || [ "$was_image" != "$image" ]; then
    fail 1 "$tag exists and names ${was_json_image:-no image}, release ${was_version:-none}: a tag is never moved"
  fi
  return 0
}

# fresh_tags: the release's own tags, every v* (the versions' and the floating ones), made origin's in one read before any
# is read: fetched by force with an explicit refspec, so that a local v* tag origin lacks is pruned, and neither a stale
# tag nor one a refused run left decides anything. A tag outside v* stays. The repository is public, so its tags are
# read with no credential; any failure stops the run with git's own words.
fresh_tags() {
  local fetched
  fetched=$(git fetch --quiet --prune origin "+refs/tags/v*:refs/tags/v*" 2>&1) || fail 1 "origin's tags could not be read: $fetched"
}

# from_of REF: where a floating tag moves from, in words: its commit now, or new.
from_of() {
  if [ -n "$1" ]; then git rev-parse --short "$1^{commit}"; else printf new; fi
}

step_plan() {
  local newest moves keep
  tools git jq
  [ "${GITHUB_REF:-}" = refs/heads/main ] || fail 2 "a release runs from main, not ${GITHUB_REF:-an unknown ref}"
  fresh_tags
  if [ -n "$rc" ] && git rev-parse -q --verify "refs/tags/v$version" > /dev/null; then
    fail 1 "v$version is released: it takes no more pre-releases"
  fi
  newest=$(newest_release)
  if [ -z "$rc" ] && [ -n "$newest" ] && newer "$newest" "$version"; then
    fail 1 "v$version is below the newest release, v$newest"
  fi
  files_present
  stamp_template "$TEMPLATE" "$TEMPLATE" "$IRONBEE_TMP/stamped.yml"
  stamp_json "$RELEASE" "$RELEASE" "$IRONBEE_TMP/stamped.json"
  if pushed; then
    notice "$tag is already pushed with this image and name: this run moves nothing, and makes the GitHub release if it is missing"
    say "tag $tag, release $name${rc:+ (a pre-release)}"
  else
    say "$tag is new${newest:+; the newest release is v$newest}"
    moves_of
    say "tag $tag, release $name${rc:+ (a pre-release)}, image $image, floating tag ${moves:-none}$(stays "$keep")"
  fi
}

# A tag on Docker Hub can be moved, and a digest can be mistyped: the release stamps the digest it was given only where
# Docker Hub holds that very image under the release's name now.
step_digest() {
  local named
  tools docker jq
  docker buildx imagetools inspect "$IMAGE:$name" --format '{{json .Manifest}}' > "$IRONBEE_TMP/hub.json" 2> "$IRONBEE_TMP/docker.err" \
    || fail 1 "could not read $IMAGE:$name: $(tail -n 1 "$IRONBEE_TMP/docker.err")"
  named=$(jq -r '.digest // empty' "$IRONBEE_TMP/hub.json" 2> /dev/null || true)
  [[ $named =~ $DIGEST ]] || fail 1 "$IMAGE:$name names no index digest"
  [ "$named" = "$digest" ] || fail 1 "$IMAGE:$name is $IMAGE@$named on Docker Hub, not the digest given, $digest"
  say "$IMAGE:$name is $image on Docker Hub, the digest given"
}

step_stamp() {
  tools jq
  files_present
  stamp_template "$TEMPLATE" "$TEMPLATE" "$IRONBEE_TMP/stamped.yml"
  stamp_json "$RELEASE" "$RELEASE" "$IRONBEE_TMP/stamped.json"
  cat "$IRONBEE_TMP/stamped.yml" > "$TEMPLATE"
  cat "$IRONBEE_TMP/stamped.json" > "$RELEASE"
  say "stamped $TEMPLATE and $RELEASE: $image (was ${was_json_image:-none}), release $name (was ${was_version:-none})"
}

step_publish() {
  local was="" latest refs leases moves keep froms now
  tools git jq
  fresh_tags
  if pushed; then
    notice "$tag is already pushed with this image and name: nothing is moved"
    return 0
  fi
  [ -z "$(git status --porcelain --untracked-files=no)" ] || fail 2 "the working tree holds changes: a release commits its stamp alone"
  step_digest
  moves_of
  step_stamp
  latest=$(git rev-parse -q --verify "refs/tags/v0" || true)
  froms=""
  git add -- "$TEMPLATE" "$RELEASE"
  # The same image and name as main already holds stamp nothing: an empty commit.
  bot commit --quiet --allow-empty -m "chore(release): $tag"
  refs=("HEAD:refs/heads/main" "refs/tags/$tag")
  leases=()
  if [ -n "$rc" ]; then
    bot tag -a "$tag" -m "$name: a pre-release for IronBee's own tests"
  else
    bot tag -a "$tag" -m "$name: a release"
    was=$(git rev-parse -q --verify "refs/tags/$floating" || true)
    froms="$floating from $(from_of "$was")"
    bot tag -f -a "$floating" -m "$floating: the newest release of major version $major ($tag)" > /dev/null
    refs+=("refs/tags/$floating")
    leases+=("--force-with-lease=refs/tags/$floating:$was")
  fi
  if [ -z "$keep" ]; then
    froms="${froms:+$froms, }v0 from $(from_of "$latest")"
    bot tag -f -a v0 -m "v0: the newest release or pre-release ($tag)" > /dev/null
  fi
  # v0 rides the push under its lease whenever there is one, moved or where it was; one that stays is an unchanged ref,
  # which carries no update for the remote to check, so it is read again right before the push.
  if git rev-parse -q --verify "refs/tags/v0" > /dev/null; then
    refs+=("refs/tags/v0")
    leases+=("--force-with-lease=refs/tags/v0:$latest")
    now=$(git ls-remote --tags origin refs/tags/v0) || fail 1 "origin's tags could not be read: nothing was pushed; run the release again"
    [ "$(awk '$2 == "refs/tags/v0" { print $1 }' <<< "$now")" = "$latest" ] \
      || fail 1 "nothing was pushed: v0 moved on origin since it was read; run the release again"
  fi
  # All or nothing. main only moves forward; the tag is new; each floating tag moves only from where it was read.
  git push --quiet --atomic ${leases[@]+"${leases[@]}"} origin "${refs[@]}" \
    || fail 1 "the push was refused and nothing was pushed: main or a tag moved meanwhile; run the release again"
  say "pushed $(git rev-parse --short HEAD) to main, tagged $tag${moves:+; $moves moved to it ($froms)}$(stays "$keep")"
}

# The GitHub release's text: the image by digest, and where the release's block and trigger app are.
notes() {
  if [ -n "$rc" ]; then
    printf '%s\n\n' "A pre-release of $version for IronBee's own tests, not for production."
  fi
  printf '%s\n\n' "Image: \`$image\`" \
    "The block: \`$TEMPLATE\` at \`$tag\`. The trigger app's source: \`trigger-app/\` at \`$tag\`." \
    "\`ironbee runner setup --host bitbucket --version $name\` sets this release up."
}

step_github_release() {
  local status pre=false
  tools git gh jq
  repository
  git ls-remote --exit-code --tags origin "refs/tags/$tag" > /dev/null || fail 1 "$tag is not pushed: a GitHub release is made for a pushed tag alone"
  status=$(api GET "repos/$IRONBEE_REPO/releases/tags/$tag" "$IRONBEE_TMP/release.json")
  case $status in
    200)
      notice "the GitHub release $tag exists: nothing to do"
      return 0
      ;;
    404) ;;
    *) fail 1 "GitHub did not say whether the release $tag exists (HTTP $status)" ;;
  esac
  notes > "$IRONBEE_TMP/notes.md"
  [ -z "$rc" ] || pre=true
  jq -n --arg tag "$tag" --rawfile notes "$IRONBEE_TMP/notes.md" --argjson pre "$pre" \
    '{tag_name: $tag, name: $tag, body: $notes, prerelease: $pre, make_latest: (if $pre then "false" else "true" end)}' \
    > "$IRONBEE_TMP/release.in.json"
  status=$(api POST "repos/$IRONBEE_REPO/releases" "$IRONBEE_TMP/release.json" "$IRONBEE_TMP/release.in.json")
  # A create GitHub made without answering is found by looking again.
  if [ "$status" != 200 ] && [ "$(api GET "repos/$IRONBEE_REPO/releases/tags/$tag" "$IRONBEE_TMP/release.json")" != 200 ]; then
    fail 1 "GitHub did not make the release $tag (HTTP $status)"
  fi
  say "made the GitHub release $tag"
}

usage="usage: release.sh plan|digest|stamp|publish|github-release"
[ $# -eq 1 ] || fail 2 "$usage"
case $1 in
  plan) inputs; digest_read; step_plan ;;
  digest) inputs; digest_read; step_digest ;;
  stamp) inputs; digest_read; step_stamp ;;
  publish) inputs; digest_read; step_publish ;;
  github-release) inputs; digest_read; step_github_release ;;
  *) fail 2 "$usage" ;;
esac
