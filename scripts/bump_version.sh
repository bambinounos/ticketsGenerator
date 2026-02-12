#!/usr/bin/env bash
# bump_version.sh - Bump semver version for server and/or Dolibarr module
#
# Usage:
#   ./scripts/bump_version.sh <component> <part>
#
#   component:  server | module | all
#   part:       major | minor | patch
#
# Examples:
#   ./scripts/bump_version.sh all patch      # 1.1.0 -> 1.1.1 (both)
#   ./scripts/bump_version.sh server minor    # 1.1.0 -> 1.2.0 (server only)
#   ./scripts/bump_version.sh module major    # 1.1.0 -> 2.0.0 (module only)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# --- Files ---
SERVER_VERSION_FILE="$ROOT_DIR/VERSION"
MOD_DESCRIPTOR="$ROOT_DIR/dolibarr_module/raffles/core/modules/modRaffles.class.php"
MOD_TRIGGER="$ROOT_DIR/dolibarr_module/raffles/core/triggers/interface_20_modRaffles_RafflesTrigger.class.php"

# --- Helpers ---
usage() {
    echo "Usage: $0 <component> <part>"
    echo ""
    echo "  component:  server | module | all"
    echo "  part:       major | minor | patch"
    echo ""
    echo "Examples:"
    echo "  $0 all patch       # Bump patch for both"
    echo "  $0 server minor    # Bump minor for server only"
    echo "  $0 module major    # Bump major for module only"
    exit 1
}

read_version() {
    local file="$1"
    tr -d '[:space:]' < "$file"
}

read_php_version() {
    local file="$1"
    grep -oP "\\\$this->version\s*=\s*'\K[0-9]+\.[0-9]+\.[0-9]+" "$file" | head -1
}

bump() {
    local version="$1"
    local part="$2"

    local major minor patch
    IFS='.' read -r major minor patch <<< "$version"

    case "$part" in
        major) major=$((major + 1)); minor=0; patch=0 ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        patch) patch=$((patch + 1)) ;;
    esac

    echo "${major}.${minor}.${patch}"
}

update_php_version() {
    local file="$1"
    local old="$2"
    local new="$3"
    sed -i "s/\$this->version = '${old}'/\$this->version = '${new}'/" "$file"
}

# --- Validation ---
if [[ $# -ne 2 ]]; then
    usage
fi

COMPONENT="$1"
PART="$2"

if [[ "$COMPONENT" != "server" && "$COMPONENT" != "module" && "$COMPONENT" != "all" ]]; then
    echo "Error: component must be 'server', 'module', or 'all'"
    usage
fi

if [[ "$PART" != "major" && "$PART" != "minor" && "$PART" != "patch" ]]; then
    echo "Error: part must be 'major', 'minor', or 'patch'"
    usage
fi

# --- Bump Server ---
if [[ "$COMPONENT" == "server" || "$COMPONENT" == "all" ]]; then
    OLD_SERVER=$(read_version "$SERVER_VERSION_FILE")
    NEW_SERVER=$(bump "$OLD_SERVER" "$PART")
    echo "$NEW_SERVER" > "$SERVER_VERSION_FILE"
    echo "Server:  $OLD_SERVER -> $NEW_SERVER  ($SERVER_VERSION_FILE)"
fi

# --- Bump Module ---
if [[ "$COMPONENT" == "module" || "$COMPONENT" == "all" ]]; then
    OLD_MODULE=$(read_php_version "$MOD_DESCRIPTOR")
    NEW_MODULE=$(bump "$OLD_MODULE" "$PART")
    update_php_version "$MOD_DESCRIPTOR" "$OLD_MODULE" "$NEW_MODULE"
    update_php_version "$MOD_TRIGGER" "$OLD_MODULE" "$NEW_MODULE"
    echo "Module:  $OLD_MODULE -> $NEW_MODULE  ($MOD_DESCRIPTOR, trigger)"
fi

echo ""
echo "Done. Review changes with 'git diff' before committing."
