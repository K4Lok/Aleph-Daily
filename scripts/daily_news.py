#!/usr/bin/env python3
"""
Daily News Aggregator - Main Orchestrator Script.

This script coordinates the entire news aggregation workflow:
1. Check/install news-aggregator-skill
2. Run Claude Code to collect news
3. Save news to dated markdown file
4. Send to Telegram (continues on failure)
5. Push to GitHub (continues on failure)

Usage:
    python scripts/daily_news.py
    python scripts/daily_news.py --preset ai_tech
    python scripts/daily_news.py --model opus
    python scripts/daily_news.py --dry-run
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from scripts.skill_manager import ensure_skill_installed
from scripts.claude_runner import run_news_aggregator
from scripts.telegram_sender import send_news_digest
from scripts.github_pusher import push_news_file


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Daily News Aggregator - Collect, format, and distribute news",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/daily_news.py                    # Use defaults from .env
    python scripts/daily_news.py --preset ai_tech   # Use AI/Tech preset
    python scripts/daily_news.py --preset china_tech --model opus
    python scripts/daily_news.py --dry-run          # Skip TG and GitHub
    python scripts/daily_news.py --list-presets     # Show available presets
        """,
    )
    
    parser.add_argument(
        "--preset",
        type=str,
        help="News preset to use (default: from .env or 'ai_tech')",
    )
    
    parser.add_argument(
        "--model",
        type=str,
        help="Claude model to use (sonnet, opus, haiku)",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without sending to TG or pushing to GitHub",
    )
    
    parser.add_argument(
        "--skip-telegram",
        action="store_true",
        help="Skip sending to Telegram",
    )
    
    parser.add_argument(
        "--skip-github",
        action="store_true",
        help="Skip pushing to GitHub",
    )
    
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List all available presets and exit",
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout for Claude command in seconds (default: 300)",
    )
    
    return parser.parse_args()


def list_presets() -> None:
    """Print all available presets."""
    presets = settings.load_presets()
    print("\n📋 Available News Presets:\n")
    
    for name, config in presets.items():
        print(f"  {name}")
        print(f"    Name: {config.get('name', 'N/A')}")
        print(f"    Description: {config.get('description', 'N/A')}")
        print(f"    Sources: {', '.join(config.get('sources', []))}")
        print()


def save_news_to_file(content: str, date_str: str) -> Path:
    """
    Save news content to a dated markdown file.
    
    Args:
        content: News content in markdown
        date_str: Date string (YYYY-MM-DD)
        
    Returns:
        Path to the saved file
    """
    # Ensure news directory exists
    settings.news_dir.mkdir(parents=True, exist_ok=True)
    
    # Create filename
    filename = f"{date_str}.md"
    file_path = settings.news_dir / filename
    
    # Add metadata header
    full_content = f"""# Daily News - {date_str}

> Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{content}
"""
    
    # Write file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_content)
    
    print(f"[Main] Saved news to {file_path}")
    return file_path


def main() -> int:
    """
    Main orchestrator function.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    args = parse_args()
    
    # Handle list-presets command
    if args.list_presets:
        list_presets()
        return 0
    
    print("=" * 60)
    print("🗞️  Daily News Aggregator")
    print("=" * 60)
    print()
    
    # Get current date
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    print(f"📅 Date: {date_str}")
    
    # Determine preset and model
    preset_name = args.preset or settings.news_preset
    model = args.model or settings.claude_model
    
    print(f"📦 Preset: {preset_name}")
    print(f"🤖 Model: {model}")
    print()
    
    # Get preset configuration
    preset = settings.get_preset(preset_name)
    if not preset:
        print(f"❌ Error: Preset '{preset_name}' not found.")
        print("   Use --list-presets to see available options.")
        return 1
    
    print(f"📰 {preset.get('name', preset_name)}")
    print(f"   {preset.get('description', '')}")
    print()
    
    # =========================================
    # Step 1: Ensure skill is installed
    # =========================================
    print("-" * 40)
    print("Step 1: Checking news-aggregator-skill...")
    print("-" * 40)
    
    success, message = ensure_skill_installed()
    if not success:
        print(f"❌ Failed to install skill: {message}")
        return 1
    print(f"✅ {message}")
    print()
    
    # =========================================
    # Step 2: Run Claude to collect news
    # =========================================
    print("-" * 40)
    print("Step 2: Collecting news via Claude Code...")
    print("-" * 40)
    
    prompt = preset.get("prompt", "")
    if not prompt:
        print("❌ Error: Preset has no prompt configured")
        return 1
    
    response = run_news_aggregator(
        preset_prompt=prompt,
        model=model,
        timeout=args.timeout,
    )
    
    if not response.success:
        print(f"❌ Failed to collect news: {response.error}")
        return 1  # Critical failure - stop here
    
    news_content = response.content
    if not news_content or len(news_content.strip()) < 50:
        print("❌ Error: Claude returned insufficient news content")
        print(f"   Content length: {len(news_content) if news_content else 0} chars")
        return 1
    
    print(f"✅ Collected news ({len(news_content)} chars)")
    print()
    
    # =========================================
    # Step 3: Save to markdown file
    # =========================================
    print("-" * 40)
    print("Step 3: Saving news to file...")
    print("-" * 40)
    
    file_path = save_news_to_file(news_content, date_str)
    print(f"✅ Saved to {file_path}")
    print()
    
    # Track results for final summary
    results = {
        "news_collected": True,
        "file_saved": True,
        "telegram_sent": None,
        "github_pushed": None,
    }
    
    # =========================================
    # Step 4: Send to Telegram (non-blocking)
    # =========================================
    if args.dry_run or args.skip_telegram:
        print("-" * 40)
        print("Step 4: Telegram - SKIPPED")
        print("-" * 40)
        results["telegram_sent"] = "skipped"
    else:
        print("-" * 40)
        print("Step 4: Sending to Telegram...")
        print("-" * 40)
        
        # Validate Telegram config
        tg_valid, tg_error = settings.validate_telegram()
        if not tg_valid:
            print(f"⚠️  Telegram not configured: {tg_error}")
            results["telegram_sent"] = False
        else:
            try:
                tg_result = send_news_digest(
                    bot_token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id,
                    news_content=news_content,
                    date_str=date_str,
                )
                
                if tg_result.success:
                    print(f"✅ Sent to Telegram (message_id: {tg_result.message_id})")
                    results["telegram_sent"] = True
                else:
                    print(f"⚠️  Telegram failed: {tg_result.error}")
                    results["telegram_sent"] = False
            except Exception as e:
                print(f"⚠️  Telegram error: {str(e)}")
                results["telegram_sent"] = False
    print()
    
    # =========================================
    # Step 5: Push to GitHub (non-blocking)
    # =========================================
    if args.dry_run or args.skip_github:
        print("-" * 40)
        print("Step 5: GitHub - SKIPPED")
        print("-" * 40)
        results["github_pushed"] = "skipped"
    else:
        print("-" * 40)
        print("Step 5: Pushing to GitHub...")
        print("-" * 40)
        
        # Validate GitHub config
        gh_valid, gh_error = settings.validate_github()
        if not gh_valid:
            print(f"⚠️  GitHub not configured: {gh_error}")
            results["github_pushed"] = False
        else:
            try:
                gh_result = push_news_file(
                    file_path=file_path,
                    date_str=date_str,
                    repo=settings.github_repo,
                    token=settings.github_token,
                    branch=settings.github_branch,
                    user_name=settings.git_user_name,
                    user_email=settings.git_user_email,
                    cwd=settings.project_root,
                )
                
                if gh_result.success:
                    print(f"✅ {gh_result.message}")
                    results["github_pushed"] = True
                else:
                    print(f"⚠️  GitHub push failed: {gh_result.error}")
                    results["github_pushed"] = False
            except Exception as e:
                print(f"⚠️  GitHub error: {str(e)}")
                results["github_pushed"] = False
    print()
    
    # =========================================
    # Final Summary
    # =========================================
    print("=" * 60)
    print("📊 Summary")
    print("=" * 60)
    print(f"  📰 News Collected: ✅")
    print(f"  💾 File Saved: ✅ ({file_path.name})")
    
    if results["telegram_sent"] == "skipped":
        print(f"  📱 Telegram: ⏭️  Skipped")
    elif results["telegram_sent"]:
        print(f"  📱 Telegram: ✅ Sent")
    else:
        print(f"  📱 Telegram: ❌ Failed")
    
    if results["github_pushed"] == "skipped":
        print(f"  🐙 GitHub: ⏭️  Skipped")
    elif results["github_pushed"]:
        print(f"  🐙 GitHub: ✅ Pushed")
    else:
        print(f"  🐙 GitHub: ❌ Failed")
    
    print()
    print("=" * 60)
    print("✨ Daily news aggregation complete!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
