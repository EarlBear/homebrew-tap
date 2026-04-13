#!/usr/bin/env bash
# agent-cli — Admin CLI for the EarlBear cloud agent (Earl).
#
# Wraps ebjira to provide agent-specific operational commands:
# queue management, status dashboards, feedback, approvals, and check-ins.
#
# Usage: agent-cli <command> [args...]
# Run `agent-cli help` for full usage.

set -euo pipefail

# ── Paths ──

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EBJIRA="$SCRIPT_DIR/ebjira"
ENV_FILE="$REPO_ROOT/.env"

# ── Load .env ──

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env not found at $REPO_ROOT. See .env.example." >&2
    exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

JIRA_PROJECT="${JIRA_PROJECT:-EARL}"
CHECKIN_EPIC_KEY="${CHECKIN_EPIC_KEY:-}"

# ── Colors ──

if command -v tput >/dev/null 2>&1 && [ -t 1 ]; then
    BOLD="$(tput bold)"
    RED="$(tput setaf 1)"
    GREEN="$(tput setaf 2)"
    YELLOW="$(tput setaf 3)"
    CYAN="$(tput setaf 6)"
    RESET="$(tput sgr0)"
else
    BOLD="" RED="" GREEN="" YELLOW="" CYAN="" RESET=""
fi

# ── Helpers ──

die() { echo "${RED}Error:${RESET} $*" >&2; exit 1; }
usage_error() { echo "${RED}Usage error:${RESET} $*" >&2; echo "Run '$(basename "$0") help' for usage." >&2; exit 2; }
header() { echo "${BOLD}${CYAN}── $* ──${RESET}"; }

require_arg() {
    if [ -z "${1:-}" ]; then
        usage_error "$2"
    fi
}

# ── Commands ──

cmd_help() {
    cat <<EOF
${BOLD}agent-cli${RESET} — Admin CLI for the EarlBear cloud agent

${BOLD}QUEUE MANAGEMENT${RESET}
  assign ISSUE_KEY          Add ai-eligible label to an issue
  assign --jql "..."        Bulk-assign ai-eligible label via JQL
  queue                     Show issues queued for agent (To Do + ai-eligible)

${BOLD}STATUS${RESET}
  status                    Dashboard: queued, drafting, in-review, rework, paused
  history ISSUE_KEY         Show full issue details with all comments

${BOLD}CHECK-INS${RESET}
  checkins                  List check-in subtasks (requires CHECKIN_EPIC_KEY in .env)
  checkin ISSUE_KEY         View a specific check-in

${BOLD}ACTIONS${RESET}
  feedback ISSUE_KEY "msg"  Transition to In Progress + add comment
  approve ISSUE_KEY         Transition to Done
  pause ISSUE_KEY "reason"  Transition to Blocked + add comment

${BOLD}HELP${RESET}
  help                      Show this message

${BOLD}ENVIRONMENT${RESET}
  JIRA_PROJECT              Jira project key (default: EARL)
  CHECKIN_EPIC_KEY          Epic key for check-in subtasks (required for 'checkins')

${BOLD}EXIT CODES${RESET}
  0  Success
  1  Error
  2  Usage error
EOF
}

cmd_assign() {
    # Bulk mode: --jql "..."
    if [ "${1:-}" = "--jql" ]; then
        require_arg "${2:-}" "assign --jql requires a JQL string"
        local jql="$2"
        header "Searching issues"
        # Get keys from JQL search
        local keys
        keys=$("$EBJIRA" issue list --jql "$jql" --format json --json "key,type,labels" 2>&1) || die "JQL search failed"

        # Parse JSON array — extract keys
        local issue_keys
        issue_keys=$(echo "$keys" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list):
    for item in data:
        print(json.dumps(item))
" 2>/dev/null) || die "Failed to parse search results"

        if [ -z "$issue_keys" ]; then
            echo "${YELLOW}No issues matched the JQL query.${RESET}"
            return 0
        fi

        local count=0
        while IFS= read -r line; do
            local key type labels
            key=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin).get('key',''))")
            type=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin).get('type',''))")
            labels=$(echo "$line" | python3 -c "import sys,json; print(' '.join(json.load(sys.stdin).get('labels',[])))")

            # Validate Deliverable has kind:* label
            if [ "$type" = "Deliverable" ]; then
                if ! echo "$labels" | grep -q "kind:"; then
                    echo "${YELLOW}SKIP${RESET} $key — Deliverable missing kind:* label"
                    continue
                fi
            fi

            # Check if already has ai-eligible
            if echo "$labels" | grep -q "ai-eligible"; then
                echo "${YELLOW}SKIP${RESET} $key — already has ai-eligible"
                continue
            fi

            # Add ai-eligible to existing labels
            local new_labels="$labels ai-eligible"
            local label_args=""
            for lbl in $new_labels; do
                label_args="$label_args --labels $lbl"
            done
            # shellcheck disable=SC2086
            "$EBJIRA" issue update "$key" $label_args --format json >/dev/null 2>&1 \
                && echo "${GREEN}OK${RESET}    $key — ai-eligible added" \
                || echo "${RED}FAIL${RESET}  $key — update failed"
            count=$((count + 1))
        done <<< "$issue_keys"

        echo ""
        echo "${BOLD}Processed $count issue(s).${RESET}"
        return 0
    fi

    # Single-issue mode
    require_arg "${1:-}" "assign requires an issue key (e.g. EARL-42)"
    local key="$1"

    header "Fetching $key"
    local issue_json
    issue_json=$("$EBJIRA" issue view "$key" --format json 2>&1) || die "Could not fetch $key"

    local type labels
    type=$(echo "$issue_json" | python3 -c "import sys,json; print(json.load(sys.stdin).get('type',''))")
    labels=$(echo "$issue_json" | python3 -c "import sys,json; print(' '.join(json.load(sys.stdin).get('labels',[])))")

    # Validate: Deliverable must have kind:* label
    if [ "$type" = "Deliverable" ]; then
        if ! echo "$labels" | grep -q "kind:"; then
            die "$key is a Deliverable but has no kind:* label. Add one before assigning."
        fi
    fi

    # Check if already has ai-eligible
    if echo "$labels" | grep -q "ai-eligible"; then
        echo "${YELLOW}$key already has ai-eligible label.${RESET}"
        return 0
    fi

    # Build label list: existing + ai-eligible
    local new_labels="$labels ai-eligible"
    local label_args=""
    for lbl in $new_labels; do
        label_args="$label_args --labels $lbl"
    done

    # shellcheck disable=SC2086
    "$EBJIRA" issue update "$key" $label_args --format json >/dev/null 2>&1 \
        || die "Failed to update labels on $key"

    echo "${GREEN}OK${RESET} Added ai-eligible label to $key"
    echo "  Type:   $type"
    echo "  Labels: $new_labels"
}

cmd_queue() {
    header "Agent Queue (Prioritized + ai-eligible)"
    "$EBJIRA" issue list \
        --jql "project = $JIRA_PROJECT AND labels = ai-eligible AND status = 'Prioritized' ORDER BY priority DESC, created ASC" \
        --format table
}

cmd_status() {
    header "Queued (Prioritized + ai-eligible)"
    "$EBJIRA" issue list \
        --jql "project = $JIRA_PROJECT AND labels = ai-eligible AND status = 'Prioritized' ORDER BY priority DESC" \
        --format table --limit 10
    echo ""

    header "Ready For Review"
    "$EBJIRA" issue list \
        --jql "project = $JIRA_PROJECT AND status = 'Ready For Review' ORDER BY updated DESC" \
        --format table --limit 10
    echo ""

    header "Rework (In Progress + ai-drafted)"
    "$EBJIRA" issue list \
        --jql "project = $JIRA_PROJECT AND status = 'In Progress' AND labels = ai-drafted ORDER BY updated DESC" \
        --format table --limit 10
    echo ""

    header "Blocked"
    "$EBJIRA" issue list \
        --jql "project = $JIRA_PROJECT AND status = 'Blocked' ORDER BY updated DESC" \
        --format table --limit 10
}

cmd_checkins() {
    if [ -z "$CHECKIN_EPIC_KEY" ]; then
        die "CHECKIN_EPIC_KEY not set in .env. Set it to the check-in epic key (e.g. EARL-31)."
    fi
    header "Check-In Subtasks ($CHECKIN_EPIC_KEY)"
    "$EBJIRA" epic children "$CHECKIN_EPIC_KEY" --format table
}

cmd_checkin() {
    require_arg "${1:-}" "checkin requires an issue key (e.g. EARL-100)"
    header "Check-In: $1"
    "$EBJIRA" issue view "$1" --format table
}

cmd_feedback() {
    require_arg "${1:-}" "feedback requires an issue key"
    require_arg "${2:-}" "feedback requires a message (e.g. feedback EARL-42 \"Please fix the header\")"
    local key="$1"
    local message="$2"

    header "Sending feedback on $key"
    "$EBJIRA" issue transition "$key" "In Progress" --comment "$message" \
        || die "Failed to transition $key to In Progress"
    echo "${GREEN}OK${RESET} $key -> In Progress with feedback comment"
}

cmd_approve() {
    require_arg "${1:-}" "approve requires an issue key"
    local key="$1"

    header "Approving $key"
    "$EBJIRA" issue transition "$key" "Done" \
        || die "Failed to transition $key to Done"
    echo "${GREEN}OK${RESET} $key -> Done"
}

cmd_pause() {
    require_arg "${1:-}" "pause requires an issue key"
    require_arg "${2:-}" "pause requires a reason (e.g. pause EARL-42 \"Missing AC\")"
    local key="$1"
    local reason="$2"

    header "Blocking $key"
    "$EBJIRA" issue transition "$key" "Blocked" --comment "$reason" \
        || die "Failed to transition $key to Blocked"
    echo "${GREEN}OK${RESET} $key -> Blocked with reason: $reason"
}

cmd_history() {
    require_arg "${1:-}" "history requires an issue key"
    header "History: $1"
    "$EBJIRA" issue view "$1" --format table
}

# ── Main dispatch ──

command="${1:-help}"
shift || true

case "$command" in
    assign)    cmd_assign "$@" ;;
    queue)     cmd_queue ;;
    status)    cmd_status ;;
    checkins)  cmd_checkins ;;
    checkin)   cmd_checkin "$@" ;;
    feedback)  cmd_feedback "$@" ;;
    approve)   cmd_approve "$@" ;;
    pause)     cmd_pause "$@" ;;
    history)   cmd_history "$@" ;;
    help|--help|-h)  cmd_help ;;
    *)         usage_error "Unknown command: $command" ;;
esac
