#!/bin/bash

# ===========================================
# Aleph Daily News - Cron Job Setup Script
# ===========================================
# This script sets up a cron job to run daily_news.py at 10:30 AM Macau time
# Usage: ./setup_cron.sh [hour] [minute]
# Example: ./setup_cron.sh 10 30  (runs at 10:30 AM)
# Example: ./setup_cron.sh       (uses default 10:30 AM)
# ===========================================

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default time: 10:30 AM Macau time (CST/UTC+8)
DEFAULT_HOUR=10
DEFAULT_MINUTE=30

# Get script directory (absolute path)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Log file location
LOG_DIR="$HOME/Library/Logs/aleph-daily"
LOG_FILE="$LOG_DIR/daily_news.log"

# Parse arguments
HOUR=${1:-$DEFAULT_HOUR}
MINUTE=${2:-$DEFAULT_MINUTE}

echo_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
echo_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
echo_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

print_header() {
    echo ""
    echo "=========================================="
    echo "  Aleph Daily News - Cron Job Setup"
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

    # Check Claude CLI
    if ! command_exists claude; then
        echo_warning "Claude CLI not found in PATH."
        echo_warning "Please install Claude Code CLI first:"
        echo_warning "  npm install -g @anthropic-ai/claude-code"
        exit 1
    fi
    echo_success "Claude CLI found: $(claude --version 2>/dev/null || echo 'installed')"

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

# Create the cron command
create_cron_command() {
    # Macau time is CST (UTC+8), no DST
    # Cron uses the system's local timezone setting

    cat <<EOF
$MINUTE $HOUR * * * cd "$SCRIPT_DIR" && $PYTHON_PATH "$SCRIPT_DIR/scripts/daily_news.py" >> "$LOG_FILE" 2>&1
EOF
}

# Remove existing cron job
remove_existing_cron() {
    echo_info "Removing existing cron jobs for Aleph Daily..."

    # Remove any existing cron job that references this project
    crontab -l 2>/dev/null | grep -v "aleph-daily\|daily_news.py" | crontab - 2>/dev/null || true

    echo_success "Old cron jobs removed"
    echo ""
}

# Install new cron job
install_cron() {
    echo_info "Installing new cron job..."

    CRON_CMD=$(create_cron_command)

    # Add new cron job
    (crontab -l 2>/dev/null; echo "$CRON_CMD # aleph-daily") | crontab -

    echo_success "Cron job installed!"
    echo ""
}

# Display summary
show_summary() {
    echo "=========================================="
    echo "  Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Cron Schedule: $HOUR:$MINUTE AM daily (Macau/CST time)"
    echo "Project Path:  $SCRIPT_DIR"
    echo "Python Path:   $PYTHON_PATH"
    echo "Log File:      $LOG_FILE"
    echo ""
    echo "To view logs:"
    echo "  tail -f $LOG_FILE"
    echo ""
    echo "To view cron jobs:"
    echo "  crontab -l"
    echo ""
    echo "To remove the cron job:"
    echo "  crontab -e  # and delete the line containing 'aleph-daily'"
    echo ""
    echo "To test manually:"
    echo "  cd $SCRIPT_DIR"
    echo "  python3 scripts/daily_news.py --dry-run"
    echo ""
    echo "=========================================="
}

# Main execution
main() {
    print_header

    # Validate time input
    if [ "$HOUR" -lt 0 ] || [ "$HOUR" -gt 23 ]; then
        echo_error "Invalid hour: $HOUR. Must be between 0 and 23."
        exit 1
    fi
    if [ "$MINUTE" -lt 0 ] || [ "$MINUTE" -gt 59 ]; then
        echo_error "Invalid minute: $MINUTE. Must be between 0 and 59."
        exit 1
    fi

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
