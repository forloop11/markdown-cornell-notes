#!/usr/bin/env bash
# Scan every commit reachable from any ref (branches + tags) in the current
# git repo for Claude/Anthropic attribution -- a "Co-Authored-By: ... claude/
# anthropic ..." trailer in the message, or an author/committer name or
# email containing "claude"/"anthropic" -- and report them.
#
# Default mode is report-only. Pass --apply to actually rewrite history and
# strip the matches (via `git filter-branch`, across --all refs). Rewriting
# changes commit hashes for every rewritten commit and everything after it,
# so this script always makes a timestamped backup ref for each branch/tag
# it touches before rewriting, and never force-pushes -- that's left to the
# user to review and do explicitly.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

APPLY=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    *) echo "Usage: $0 [--apply]" >&2; exit 1 ;;
  esac
done

PATTERN='claude|anthropic'

echo "Scanning all commits reachable from any ref for Claude/Anthropic attribution..."

matches=$(git log --all --format='%H' | while read -r h; do
  msg=$(git log -1 --format='%B' "$h")
  author=$(git log -1 --format='%an <%ae>' "$h")
  committer=$(git log -1 --format='%cn <%ce>' "$h")
  if grep -qiE "co-authored-by:.*($PATTERN)" <<<"$msg" \
     || grep -qiE "generated (with|by).*($PATTERN)" <<<"$msg" \
     || grep -qiE "$PATTERN" <<<"$author" \
     || grep -qiE "$PATTERN" <<<"$committer"; then
    echo "$h"
  fi
done)

if [ -z "$matches" ]; then
  echo "No Claude/Anthropic attribution found in any reachable commit."
  exit 0
fi

echo "Found attribution in these commits:"
while read -r h; do
  echo "--- $h ---"
  git log -1 --format='author:    %an <%ae>%ncommitter: %cn <%ce>%nsubject:   %s' "$h"
  git log -1 --format='%B' "$h" | grep -iE "co-authored-by:.*($PATTERN)|generated (with|by).*($PATTERN)" || true
  echo
done <<<"$matches"

if [ "$APPLY" -ne 1 ]; then
  echo "Report-only run (default). Re-run with --apply to rewrite history and strip these."
  exit 0
fi

if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  echo "Working tree has uncommitted changes -- commit or stash before rewriting history." >&2
  exit 1
fi

backup_suffix="backup/pre-claude-strip-$(date +%Y%m%d%H%M%S)"
echo "Backing up refs under $backup_suffix/ before rewriting..."
git for-each-ref --format='%(refname)' refs/heads refs/tags | while read -r ref; do
  short=${ref#refs/heads/}
  short=${short#refs/tags/}
  git branch "$backup_suffix/$short" "$ref"
done

echo "Rewriting commit messages and author/committer identity across all branches and tags..."
git filter-branch -f \
  --msg-filter '
    grep -viE "^co-authored-by:.*('"$PATTERN"')" | \
    grep -viE "^.*generated (with|by).*('"$PATTERN"')"
  ' \
  --env-filter '
    if echo "$GIT_AUTHOR_NAME $GIT_AUTHOR_EMAIL" | grep -qiE "'"$PATTERN"'"; then
      export GIT_AUTHOR_NAME="$(git config user.name)"
      export GIT_AUTHOR_EMAIL="$(git config user.email)"
    fi
    if echo "$GIT_COMMITTER_NAME $GIT_COMMITTER_EMAIL" | grep -qiE "'"$PATTERN"'"; then
      export GIT_COMMITTER_NAME="$(git config user.name)"
      export GIT_COMMITTER_EMAIL="$(git config user.email)"
    fi
  ' \
  --tag-name-filter cat \
  -- --all

echo "Done. refs/original/* and the $backup_suffix/* branches hold the pre-rewrite state."
echo "Review with 'git log --all', then force-push the affected branches/tags yourself when ready:"
echo "  git push --force-with-lease origin <branch>"
echo "Nothing was pushed or force-pushed by this script."
