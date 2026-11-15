# Shared by the release's scripts, sourced and never run: the log, GitHub's API through gh, and the repository. Needs
# bash, jq and gh. Every value of an answer is read with jq from a file; none is ever evaluated as code.
# shellcheck disable=SC2034  # the values set here are read by the scripts that source this file

IRONBEE_SCRIPTS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export GH_NO_UPDATE_NOTIFIER=1 GH_PROMPT_DISABLED=1

IRONBEE_TMP=$(mktemp -d)
trap 'rm -rf "$IRONBEE_TMP"' EXIT

say() { printf '%s\n' "$*"; }

# command_text TEXT...: the text escaped as GitHub reads a workflow command's (`%`, CR and LF), so none of it can start
# a command line of its own.
command_text() {
  local text=$*
  text=${text//"%"/%25}
  text=${text//$'\r'/%0D}
  text=${text//$'\n'/%0A}
  printf '%s' "$text"
}

# fail CODE TEXT...: an error annotation, then the exit: 1 a refusal or a call that failed, 2 the inputs, the
# repository or the machine.
fail() {
  local code=$1
  shift
  printf '::error::%s\n' "$(command_text "$*")"
  exit "$code"
}

notice() { printf '::notice::%s\n' "$(command_text "$*")"; }

# tools TOOL...: each on the PATH, or an error naming it.
tools() {
  local tool
  for tool in "$@"; do
    command -v "$tool" > /dev/null || fail 2 "$tool is not installed on this machine"
  done
}

repository() {
  IRONBEE_REPO=${GITHUB_REPOSITORY:-}
  case $IRONBEE_REPO in */*/* | /* | */ | *[[:space:]]* | '') fail 2 "GITHUB_REPOSITORY names no repository (owner/name)" ;; esac
  case $IRONBEE_REPO in */*) ;; *) fail 2 "GITHUB_REPOSITORY names no repository (owner/name)" ;; esac
}

# api METHOD PATH OUT [IN]: one call of GitHub's REST API through gh, as GH_TOKEN; the answer's body in OUT and its HTTP
# status printed: 200 for any success, 000 when no answer came. No answer, a 429 or a 5xx is tried three times in all; a
# POST only on a 429, since one that got no answer or a 5xx may have made what it asked, which its caller looks for. IN
# is the request's JSON body.
api() {
  local method=$1 path=$2 out=$3 in=${4:-} n status=000
  for n in 1 2 3; do
    case $n in 2) sleep 2 ;; 3) sleep 5 ;; esac
    if gh api --method "$method" ${in:+--input "$in"} "$path" > "$out" 2> "$IRONBEE_TMP/gh.err"; then
      echo 200
      return 0
    fi
    status=$(grep -o 'HTTP [0-9][0-9][0-9]' "$IRONBEE_TMP/gh.err" | tail -n 1 | cut -c6-)
    status=${status:-000}
    case $status in 000 | 429 | 5??) ;; *) break ;; esac
    if [ "$method" = POST ] && [ "$status" != 429 ]; then
      break
    fi
  done
  echo "$status"
}
