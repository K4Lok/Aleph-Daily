#!/bin/bash

# ===========================================
# Aleph Daily News - Cron Job Setup Script (FIXED VERSION)
# ===========================================
# This script sets up cron jobs with:
#   1. Fixed PATH for Claude CLI
#   2. Enhanced monitoring via wrapper script
#   3. Telegram notifications for all runs
#
# Jobs scheduled:
#   1. Morning tech news at 10:30 AM (preset: ai_tech)
#   2. Evening finance news at 21:00 PM (preset: finance)
#
# Usage: ./setup_cron_fixed.sh
# ===========================================

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory (absolute path)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Log file location
LOG_DIR="$HOME/Library/Logs/aleph-daily"
LOG_FILE="$LOG_DIR/daily_news.log"

# ---- Scheduled Jobs Configuration ----
# Format: "MINUTE HOUR PRESET TAG"
JOBS=(
    "30 10 ai_tech aleph-daily-tech"
    "0 21 finance aleph-daily-finance"
)

echo_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
echo_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
echo_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

print_header() {
    echo ""
    echo "=========================================="
    echo "  Aleph Daily News - Cron Job Setup"
    echo "  (FIXED VERSION with PATH and Wrapper)"
    echo "=========================================="
    echo ""
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python and dependencies
check_dependencies() {
    echo_info "Checking dependencies..."

    # Check Python 3
    if ! command_exists python3; then
        echo_error "Python 3 is not installed. Please install Python 3 first."
        exit 1
    fi
    echo_success "Python 3 found: $(python3 --version)"

    # Check pip3
    if ! command_exists pip3; then
        echo_error "pip3 is not installed."
        exit 1
    fi
    echo_success "pip3 found"

    # Check CCS CLI
    CCS_PATH=$(which ccs 2>/dev/null || echo "")
    if [ -z "$CCS_PATH" ]; then
        echo_warning "CCS CLI not found in PATH."
        echo_warning "Please install CCS first:"
        echo_warning "  npm install -g @kaitranntt/ccs"
        exit 1
    fi
    echo_success "CCS CLI found at: $CCS_PATH"

    # Check Git
    if ! command_exists git; then
        echo_error "Git is not installed."
        exit 1
    fi
    echo_success "Git found: $(git --version)"

    echo ""
}

# Install Python dependencies
install_python_deps() {
    echo_info "Installing Python dependencies..."

    cd "$SCRIPT_DIR"

    if [ ! -f "requirements.txt" ]; then
        echo_error "requirements.txt not found in $SCRIPT_DIR"
        exit 1
    fi

    # Add requests if not in requirements.txt (needed for wrapper)
    if ! grep -q "requests" requirements.txt; then
        echo_info "Adding 'requests' to requirements.txt..."
        echo "requests>=2.31.0" >> requirements.txt
    fi

    # Use virtual environment if it exists, otherwise create it
    if [ -f "venv/bin/python" ]; then
        echo_info "Using existing virtual environment..."
        venv/bin/pip install -q -r requirements.txt
    else
        echo_info "Creating virtual environment..."
        python3 -m venv venv
        venv/bin/pip install -q -r requirements.txt
    fi

    echo_success "Python dependencies installed in venv/"
    echo ""
}

# Check .env file
check_env_file() {
    echo_info "Checking environment configuration..."

    ENV_FILE="$SCRIPT_DIR/.env"

    if [ ! -f "$ENV_FILE" ]; then
        echo_warning ".env file not found."
        echo_warning "Creating .env from .env.example..."
        cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
        echo_warning "Please edit $ENV_FILE with your actual configuration:"
        echo_warning "  - TELEGRAM_BOT_TOKEN"
        echo_warning "  - TELEGRAM_CHAT_ID"
        echo_warning "  - GITHUB_TOKEN"
        echo_warning "  - GITHUB_REPO"
        echo_warning "  - GIT_USER_NAME"
        echo_warning "  - GIT_USER_EMAIL"
        echo ""
        read -p "Press Enter after configuring .env to continue..."
    fi

    echo_success "Environment file exists"
    echo ""
}

# Create log directory
setup_logging() {
    echo_info "Setting up logging..."

    mkdir -p "$LOG_DIR"
    touch "$LOG_FILE"

    echo_success "Log directory created: $LOG_DIR"
    echo ""
}

# Get the Python path - prefer virtual environment if it exists
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    PYTHON_PATH="$VENV_PYTHON"
else
    PYTHON_PATH=$(which python3)
fi

# Get PATH for cron (includes homebrew, etc.)
# This fixes the "Claude CLI not found" issue
FULL_PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
CCS_BIN=$(which ccs 2>/dev/null || echo "/opt/homebrew/bin/ccs")

# Remove existing cron jobs
remove_existing_cron() {
    echo_info "Removing existing cron jobs for Aleph Daily..."

    # Remove any existing cron job that references this project
    crontab -l 2>/dev/null | grep -v "aleph-daily\|daily_news.py\|cron_wrapper.py" | crontab - 2>/dev/null || true

    echo_success "Old cron jobs removed"
    echo ""
}

# Install all scheduled cron jobs with wrapper
install_cron() {
    echo_info "Installing cron jobs with enhanced monitoring..."
    echo_warning "Using cron_wrapper.py for notifications and logging"
    echo ""

    # Macau time is CST (UTC+8), no DST
    # Cron uses the system's local timezone setting

    EXISTING_CRON=$(crontab -l 2>/dev/null || true)

    for job in "${JOBS[@]}"; do
        read -r JOB_MINUTE JOB_HOUR JOB_PRESET JOB_TAG <<< "$job"

        # Use wrapper script with PATH set
        CRON_LINE="$JOB_MINUTE $JOB_HOUR * * * export PATH=\"$FULL_PATH:\$PATH\" && cd \"$SCRIPT_DIR\" && $PYTHON_PATH \"$SCRIPT_DIR/scripts/cron_wrapper.py\" --preset $JOB_PRESET >> \"$LOG_FILE\" 2>&1 # $JOB_TAG"

        EXISTING_CRON="$EXISTING_CRON
$CRON_LINE"

        echo_success "  [$JOB_TAG] $(printf '%02d:%02d' $JOB_HOUR $JOB_MINUTE) daily → preset: $JOB_PRESET (with wrapper)"
    done

    echo "$EXISTING_CRON" | crontab -

    echo ""
}

# Display summary
show_summary() {
    echo "=========================================="
    echo "  Setup Complete!"
    echo "=========================================="
    echo ""
    echo "✨ NEW FEATURES:"
    echo "  ✅ Fixed PATH issue (Claude CLI now accessible)"
    echo "  ✅ Enhanced monitoring via cron_wrapper.py"
    echo "  ✅ Telegram notifications for every run"
    echo "  ✅ Detailed error reporting"
    echo ""
    echo "Scheduled Jobs:"
    for job in "${JOBS[@]}"; do
        read -r JOB_MINUTE JOB_HOUR JOB_PRESET JOB_TAG <<< "$job"
        echo "  - [$JOB_TAG] $(printf '%02d:%02d' $JOB_HOUR $JOB_MINUTE) daily → preset: $JOB_PRESET"
    done
    echo ""
    echo "Project Path:  $SCRIPT_DIR"
    echo "Python Path:   $PYTHON_PATH"
    echo "CCS Path:      $CCS_BIN"
    echo "Log File:      $LOG_FILE"
    echo ""
    echo "Telegram Notifications:"
    echo "  🚀 Cron start notification"
    echo "  ✅ Success notification (with news count)"
    echo "  ❌ Failure notification (with error details)"
    echo "  ⏰ Timeout notification (if script hangs)"
    echo ""
    echo "To view logs:"
    echo "  tail -f $LOG_FILE"
    echo ""
    echo "To view cron jobs:"
    echo "  crontab -l"
    echo ""
    echo "To remove cron jobs:"
    echo "  crontab -e  # and delete lines containing 'aleph-daily'"
    echo ""
    echo "To test manually (with wrapper):"
    echo "  cd $SCRIPT_DIR"
    echo "  python3 scripts/cron_wrapper.py --preset ai_tech --dry-run"
    echo "  python3 scripts/cron_wrapper.py --preset finance"
    echo ""
    echo "To test original script (without wrapper):"
    echo "  cd $SCRIPT_DIR"
    echo "  python3 scripts/daily_news.py --preset ai_tech --dry-run"
    echo ""
    echo "⏰ Next runs:"
    echo "  - Tech News:    Today 10:30 AM"
    echo "  - Finance News: Today 09:00 PM"
    echo ""
    echo "=========================================="
}

# Main execution
main() {
    print_header
    check_dependencies
    install_python_deps
    check_env_file
    setup_logging
    remove_existing_cron
    install_cron
    show_summary
}

# Run main
main "$@"
