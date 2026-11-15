#!/usr/bin/env bash
# Say whether the project template has a newer version than this project was generated from.
# Prints the steps to update when it does, and nothing when the project is current or the
# template cannot be reached. Always exits 0, so it is safe to run at the start of every session.
# Usage: bash scripts/template-update.sh
# Env: TEMPLATE_UPDATE_TIMEOUT (seconds to wait for the template's tag list, default 15)
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
answers="$root/.copier-answers.yml"
[ -f "$answers" ] || exit 0

field() { sed -n "s/^$1:[[:space:]]*//p" "$answers" | head -n 1 | tr -d "'\"" | tr -d '\r'; }
source_path="$(field _src_path)"
recorded="$(field _commit)"
[ -n "$source_path" ] && [ -n "$recorded" ] || exit 0

# A project generated between two tags records `v1.2.0-4-gabc1234`: it is at least at v1.2.0.
current="$(printf '%s\n' "$recorded" | sed 's/-[0-9][0-9]*-g[0-9a-f]*$//')"
case "$current" in v[0-9]*) ;; *) exit 0 ;; esac

latest="$(GIT_TERMINAL_PROMPT=0 timeout "${TEMPLATE_UPDATE_TIMEOUT:-15}" \
  git ls-remote --tags --refs "$source_path" 'v[0-9]*' 2>/dev/null |
  sed 's|.*refs/tags/||' | sort -V | tail -n 1)"
[ -n "$latest" ] && [ "$latest" != "$current" ] || exit 0
[ "$(printf '%s\n%s\n' "$current" "$latest" | sort -V | tail -n 1)" = "$latest" ] || exit 0

cat <<EOF
Template update available: this project is at $recorded and the template ($source_path) is at $latest.
Update before starting other work, unless the user says not to:
1. Run \`git status --porcelain\`. If it prints anything, tell the user the update is waiting on uncommitted changes and carry on with their request.
2. Run \`uvx copier update --trust --defaults --skip-answered --conflict inline\`.
3. Read the template's CHANGELOG.md for every version after $current up to $latest and do each "Manual action in existing projects".
4. Resolve every conflict marker (\`<<<<<<<\`), keeping the project's own code and taking the template's tooling and rules.
5. Run the project's check command and fix what fails.
6. Commit as \`chore: update to template $latest\` and push.
If a step cannot be finished, run \`git reset --hard && git clean -fd\` to return to the last commit, and tell the user what blocked it.
EOF
