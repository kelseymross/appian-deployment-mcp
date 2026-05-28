#!/bin/bash
# Appian Deployment MCP Server - Interactive Setup
# This script helps you configure the MCP server with your Appian environments.

set -e

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  Appian Deployment MCP Server Setup          ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""

# --- Check prerequisites ---
echo -e "${CYAN}Checking prerequisites...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is required but not installed.${NC}"
    echo "  Install it from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo -e "${RED}✗ Python 3.11+ is required (found $PYTHON_VERSION).${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"

if command -v uv &> /dev/null; then
    echo -e "${GREEN}✓${NC} uv found"
    USE_UV=true
else
    echo -e "${YELLOW}!${NC} uv not found (will use pip instead)"
    USE_UV=false
fi

# --- Install dependencies ---
echo ""
echo -e "${CYAN}Installing dependencies...${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ "$USE_UV" = true ]; then
    uv sync --quiet 2>/dev/null || uv sync
else
    python3 -m venv .venv 2>/dev/null || true
    .venv/bin/pip install -e . --quiet 2>/dev/null || .venv/bin/pip install -e .
fi

ENTRY_POINT="$SCRIPT_DIR/.venv/bin/appian-deployment"
if [ ! -f "$ENTRY_POINT" ]; then
    echo -e "${RED}✗ Entry point not found at $ENTRY_POINT${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Server installed at $ENTRY_POINT"

# --- Configure environments ---
echo ""
echo -e "${BOLD}Configure your Appian environments${NC}"
echo -e "${DIM}You can add multiple environments (dev, test, prod, etc.)${NC}"
echo ""

ENVIRONMENTS=()
ENV_JSON_PARTS=()

add_environment() {
    local env_name="$1"
    local env_upper=$(echo "$env_name" | tr '[:lower:]' '[:upper:]')

    echo ""
    echo -e "${CYAN}--- Environment: ${BOLD}$env_name${NC} ---"
    echo ""

    read -p "  Appian domain (e.g. mysite.appiancloud.com): " domain
    if [ -z "$domain" ]; then
        echo -e "${RED}  Domain is required. Skipping this environment.${NC}"
        return
    fi

    echo ""
    echo "  How would you like to store your API key?"
    echo "    1) Plaintext in config (simple, less secure)"
    echo "    2) System keychain (recommended, more secure)"
    echo "    3) OAuth token"
    echo ""
    read -p "  Choice [1/2/3]: " auth_choice

    case "$auth_choice" in
        2)
            # Keychain
            local service="appian-${env_name}-api-key"
            read -p "  Keychain service name [$service]: " custom_service
            service="${custom_service:-$service}"

            echo ""
            read -s -p "  Enter your API key (hidden): " api_key
            echo ""

            if [ -z "$api_key" ]; then
                echo -e "${RED}  API key is required.${NC}"
                return
            fi

            # Store in keychain
            local account="appian-deployment-mcp"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS - delete existing entry if present, then add
                security delete-generic-password -s "$service" -a "$account" 2>/dev/null || true
                security add-generic-password -s "$service" -a "$account" -w "$api_key"
                echo -e "  ${GREEN}✓${NC} API key stored in macOS Keychain (service: $service)"
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                if command -v secret-tool &> /dev/null; then
                    echo "$api_key" | secret-tool store --label="$service" service "$service" account "$account"
                    echo -e "  ${GREEN}✓${NC} API key stored in Secret Service (service: $service)"
                else
                    echo -e "${YELLOW}  ! secret-tool not found. Install libsecret-tools and re-run.${NC}"
                    echo -e "  Falling back to plaintext."
                    ENV_JSON_PARTS+=("        \"APPIAN_${env_upper}_DOMAIN\": \"$domain\"")
                    ENV_JSON_PARTS+=("        \"APPIAN_${env_upper}_API_KEY\": \"$api_key\"")
                    ENVIRONMENTS+=("$env_name")
                    return
                fi
            fi

            ENV_JSON_PARTS+=("        \"APPIAN_${env_upper}_DOMAIN\": \"$domain\"")
            ENV_JSON_PARTS+=("        \"APPIAN_${env_upper}_API_KEY_SOURCE\": \"keychain\"")
            ENV_JSON_PARTS+=("        \"APPIAN_${env_upper}_API_KEY_SERVICE\": \"$service\"")
            ;;
        3)
            # OAuth
            read -s -p "  Enter your OAuth token (hidden): " oauth_token
            echo ""
            ENV_JSON_PARTS+=("        \"APPIAN_${env_upper}_DOMAIN\": \"$domain\"")
            ENV_JSON_PARTS+=("        \"APPIAN_${env_upper}_OAUTH_TOKEN\": \"$oauth_token\"")
            ;;
        *)
            # Plaintext
            read -s -p "  Enter your API key (hidden): " api_key
            echo ""
            ENV_JSON_PARTS+=("        \"APPIAN_${env_upper}_DOMAIN\": \"$domain\"")
            ENV_JSON_PARTS+=("        \"APPIAN_${env_upper}_API_KEY\": \"$api_key\"")
            ;;
    esac

    ENVIRONMENTS+=("$env_name")
    echo -e "  ${GREEN}✓${NC} Environment '$env_name' configured"
}

# First environment
read -p "Environment name (e.g. dev, test, prod): " first_env
add_environment "$first_env"

# Additional environments
while true; do
    echo ""
    read -p "Add another environment? [y/N]: " add_more
    if [[ "$add_more" =~ ^[Yy] ]]; then
        read -p "Environment name: " next_env
        add_environment "$next_env"
    else
        break
    fi
done

if [ ${#ENVIRONMENTS[@]} -eq 0 ]; then
    echo -e "${RED}No environments configured. Exiting.${NC}"
    exit 1
fi

# --- Generate MCP config ---
echo ""
echo -e "${CYAN}Generating MCP configuration...${NC}"
echo ""

# Build the env JSON
ENV_LINES=$(printf ",\n%s" "${ENV_JSON_PARTS[@]}")
ENV_LINES="${ENV_LINES:2}" # Remove leading comma and newline

MCP_CONFIG=$(cat <<EOF
{
  "mcpServers": {
    "appian-deployment": {
      "command": "$ENTRY_POINT",
      "args": [],
      "env": {
$ENV_LINES
      }
    }
  }
}
EOF
)

echo -e "${BOLD}Your MCP configuration:${NC}"
echo ""
# Redact sensitive values before displaying
DISPLAY_CONFIG=$(echo "$MCP_CONFIG" | sed -E 's/("APPIAN_[A-Z_]*_(API_KEY|OAUTH_TOKEN)":\s*")[^"]+"/\1<REDACTED>"/g')
echo "$DISPLAY_CONFIG"
echo ""
echo -e "${DIM}(Sensitive values are redacted above. The saved file will contain actual values.)${NC}"
echo ""

# --- Offer to save ---
echo -e "${CYAN}Where would you like to save this config?${NC}"
echo "  1) .kiro/settings/mcp.json (workspace - for this project)"
echo "  2) ~/.kiro/settings/mcp.json (user - for all projects)"
echo "  3) Copy to clipboard only"
echo "  4) Print only (already shown above)"
echo ""
read -p "Choice [1/2/3/4]: " save_choice

case "$save_choice" in
    1)
        mkdir -p .kiro/settings
        echo "$MCP_CONFIG" > .kiro/settings/mcp.json
        echo -e "${GREEN}✓${NC} Saved to .kiro/settings/mcp.json"
        ;;
    2)
        mkdir -p ~/.kiro/settings
        if [ -f ~/.kiro/settings/mcp.json ]; then
            echo -e "${YELLOW}! ~/.kiro/settings/mcp.json already exists.${NC}"
            read -p "  Overwrite? [y/N]: " overwrite
            if [[ "$overwrite" =~ ^[Yy] ]]; then
                echo "$MCP_CONFIG" > ~/.kiro/settings/mcp.json
                echo -e "${GREEN}✓${NC} Saved to ~/.kiro/settings/mcp.json"
            else
                echo "  Skipped."
            fi
        else
            echo "$MCP_CONFIG" > ~/.kiro/settings/mcp.json
            echo -e "${GREEN}✓${NC} Saved to ~/.kiro/settings/mcp.json"
        fi
        ;;
    3)
        if command -v pbcopy &> /dev/null; then
            echo "$MCP_CONFIG" | pbcopy
            echo -e "${GREEN}✓${NC} Copied to clipboard (pbcopy)"
        elif command -v xclip &> /dev/null; then
            echo "$MCP_CONFIG" | xclip -selection clipboard
            echo -e "${GREEN}✓${NC} Copied to clipboard (xclip)"
        else
            echo -e "${YELLOW}! No clipboard tool found. Config printed above.${NC}"
        fi
        ;;
    *)
        echo "  Config printed above (with redacted secrets)."
        echo "  Use option 1, 2, or 3 to get the full config with actual values."
        ;;
esac

# --- Done ---
echo ""
echo -e "${GREEN}${BOLD}Setup complete!${NC}"
echo ""
echo "  Configured environments: ${ENVIRONMENTS[*]}"
echo "  Server path: $ENTRY_POINT"
echo ""
echo -e "${DIM}Next steps:${NC}"
echo "  1. Restart your MCP client (Kiro, Claude Desktop, etc.)"
echo "  2. The appian-deployment tools should now be available"
echo "  3. Try: \"List my Appian environments\""
echo ""
