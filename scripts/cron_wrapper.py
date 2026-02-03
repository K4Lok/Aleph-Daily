#!/usr/bin/env python3
"""
Cron Wrapper Script - Enhanced Monitoring and Notifications

This wrapper script:
1. Captures all output from daily_news.py
2. Logs execution status (start, success, failure)
3. Sends Telegram notifications for all execution attempts
4. Provides detailed error reporting

Usage:
    python scripts/cron_wrapper.py --preset finance
    python scripts/cron_wrapper.py --preset ai_tech --model opus
"""

import argparse
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
import requests


def send_telegram_notification(message: str, parse_mode: str = "Markdown") -> bool:
    """
    Send a notification to Telegram.

    Args:
        message: Message text to send
        parse_mode: Telegram parse mode (Markdown or HTML)

    Returns:
        True if sent successfully, False otherwise
    """
    # Validate Telegram config
    tg_valid, tg_error = settings.validate_telegram()
    if not tg_valid:
        print(f"[Telegram] Not configured: {tg_error}")
        return False

    try:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        data = {
            "chat_id": settings.telegram_chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()

        print(f"[Telegram] Notification sent successfully")
        return True

    except Exception as e:
        print(f"[Telegram] Failed to send notification: {e}")
        return False


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def main():
    """Main wrapper function."""
    parser = argparse.ArgumentParser(description="Cron Wrapper with Enhanced Monitoring")
    parser.add_argument("--preset", type=str, help="News preset to use")
    parser.add_argument("--model", type=str, help="Claude model to use")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    parser.add_argument("--no-streaming", action="store_true", help="Disable streaming")
    parser.add_argument("--skip-telegram", action="store_true", help="Skip Telegram")
    parser.add_argument("--skip-github", action="store_true", help="Skip GitHub")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    args = parser.parse_args()

    # Get current timestamp
    start_time = datetime.now()
    timestamp = start_time.strftime("%Y-%m-%d %H:%M:%S")
    date_str = start_time.strftime("%Y-%m-%d")

    # Determine preset
    preset_name = args.preset or settings.news_preset or "ai_tech"
    model = args.model or settings.claude_model or "sonnet"

    # Get preset info
    preset = settings.get_preset(preset_name)
    preset_display = preset.get("name", preset_name) if preset else preset_name

    print("=" * 80)
    print(f"🚀 Cron Wrapper - Starting at {timestamp}")
    print("=" * 80)
    print(f"📦 Preset: {preset_name} ({preset_display})")
    print(f"🤖 Model: {model}")
    print(f"📅 Date: {date_str}")
    print()

    # Send start notification
    start_message = f"""
🚀 *Aleph Daily - Cron Started*

📅 Date: `{date_str}`
⏰ Time: `{timestamp}`
📦 Preset: *{preset_display}*
🤖 Model: `{model}`

⏳ Collecting news...
"""
    send_telegram_notification(start_message.strip())

    # Build command to run daily_news.py
    python_path = sys.executable
    script_path = Path(__file__).parent / "daily_news.py"

    cmd = [python_path, str(script_path)]

    if args.preset:
        cmd.extend(["--preset", args.preset])
    if args.model:
        cmd.extend(["--model", args.model])
    if args.timeout:
        cmd.extend(["--timeout", str(args.timeout)])
    if args.no_streaming:
        cmd.append("--no-streaming")
    if args.skip_telegram:
        cmd.append("--skip-telegram")
    if args.skip_github:
        cmd.append("--skip-github")
    if args.dry_run:
        cmd.append("--dry-run")

    print(f"[Wrapper] Running command: {' '.join(cmd)}")
    print()

    # Run the script and capture output
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=args.timeout + 60,  # Extra buffer for script overhead
        )

        # Calculate duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        duration_str = format_duration(duration)

        # Print captured output
        print("=" * 80)
        print("📋 Script Output:")
        print("=" * 80)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        print()

        # Check exit code
        if result.returncode == 0:
            # Success
            print("=" * 80)
            print(f"✅ Cron Completed Successfully in {duration_str}")
            print("=" * 80)

            # Parse output for news count
            news_count = 0
            if "成功收集" in result.stdout:
                import re
                match = re.search(r'成功收集\s+(\d+)\s+則新聞', result.stdout)
                if match:
                    news_count = int(match.group(1))

            # Send success notification
            success_message = f"""
✅ *Aleph Daily - Success*

📅 Date: `{date_str}`
📦 Preset: *{preset_display}*
📰 News Collected: *{news_count} items*
⏱️ Duration: `{duration_str}`

🔗 Check your news in the archive!
"""
            send_telegram_notification(success_message.strip())

            return 0

        else:
            # Failure
            print("=" * 80)
            print(f"❌ Cron Failed with exit code {result.returncode}")
            print("=" * 80)

            # Extract error message from output
            error_lines = []
            for line in result.stdout.split('\n'):
                if '❌' in line or 'Error' in line or 'Failed' in line:
                    error_lines.append(line.strip())

            error_summary = '\n'.join(error_lines[-5:]) if error_lines else "Unknown error"

            # Send failure notification
            failure_message = f"""
❌ *Aleph Daily - Failed*

📅 Date: `{date_str}`
📦 Preset: *{preset_display}*
⏱️ Duration: `{duration_str}`
🔴 Exit Code: `{result.returncode}`

**Error:**
```
{error_summary[:500]}
```

💡 Check logs at:
`~/Library/Logs/aleph-daily/daily_news.log`
"""
            send_telegram_notification(failure_message.strip())

            return 1

    except subprocess.TimeoutExpired:
        # Timeout
        duration = args.timeout + 60
        duration_str = format_duration(duration)

        print("=" * 80)
        print(f"⏰ Cron Timeout after {duration_str}")
        print("=" * 80)

        timeout_message = f"""
⏰ *Aleph Daily - Timeout*

📅 Date: `{date_str}`
📦 Preset: *{preset_display}*
⏱️ Timeout: `{duration_str}`

⚠️ The script took too long to complete.
Check if there are network issues or if the Claude API is slow.

💡 Check logs at:
`~/Library/Logs/aleph-daily/daily_news.log`
"""
        send_telegram_notification(timeout_message.strip())

        return 1

    except Exception as e:
        # Unexpected error
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        duration_str = format_duration(duration)

        print("=" * 80)
        print(f"💥 Unexpected Error in Cron Wrapper")
        print("=" * 80)
        print(traceback.format_exc())

        error_message = f"""
💥 *Aleph Daily - Wrapper Error*

📅 Date: `{date_str}`
📦 Preset: *{preset_display}*
⏱️ Duration: `{duration_str}`

**Error:**
```
{str(e)[:500]}
```

💡 This is a wrapper script error, not a daily_news.py error.
Check logs for details.
"""
        send_telegram_notification(error_message.strip())

        return 1


if __name__ == "__main__":
    sys.exit(main())
