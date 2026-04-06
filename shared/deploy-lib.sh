#!/bin/bash
# Shared deployment utilities

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Load .env file
load_env() {
  local env_file="${1:-.env}"
  if [[ ! -f "$env_file" ]]; then
    log_error ".env file not found at $env_file"
    exit 1
  fi
  set -a
  source "$env_file"
  set +a
  log_info "Loaded environment from $env_file"
}

# Validate Stripe key is set
validate_stripe_key() {
  if [[ -z "$STRIPE_SECRET_KEY" ]]; then
    log_error "STRIPE_SECRET_KEY not set in .env"
    exit 1
  fi
  if [[ ! "$STRIPE_SECRET_KEY" =~ ^sk_(test|live)_ ]]; then
    log_error "Invalid Stripe key format"
    exit 1
  fi
  log_info "Stripe key validated"
}

# Check GitHub CLI auth
check_gh_auth() {
  if ! command -v gh &>/dev/null; then
    log_error "GitHub CLI (gh) not installed"
    exit 1
  fi
  if ! gh auth status &>/dev/null; then
    log_error "GitHub CLI not authenticated. Run: gh auth login"
    exit 1
  fi
  log_info "GitHub CLI authenticated"
}

# Check Netlify CLI auth
check_netlify_auth() {
  if ! command -v netlify &>/dev/null; then
    log_error "Netlify CLI not installed. Run: npm install -g netlify-cli"
    exit 1
  fi
  log_info "Netlify CLI available"
}
