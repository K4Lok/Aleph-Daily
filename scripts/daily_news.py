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
import re
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


def count_news_items(content: str) -> int:
    """
    Count the number of news items in the content.
    Looks for patterns like numbered headers or --- separators.
    """
    # Count --- separators
    separator_count = len(re.findall(r'\n---+\n', content))
    if separator_count > 0:
        return separator_count
    
    # Count numbered headers like "### 1.", "## 1.", "1.", etc.
    numbered_headers = re.findall(r'(?:^|\n)(?:#{1,3}\s*)?\d+[\.\)、]', content)
    if numbered_headers:
        return len(numbered_headers)
    
    return 0


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
    
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Disable streaming output (use batch mode instead)",
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
    
    use_streaming = not args.no_streaming
    if use_streaming:
        print("   ⏳ 正在收集新聞（串流模式）...")
        print("   (這可能需要 1-3 分鐘，取決於新聞來源)")
        print()
    else:
        print("   ⏳ 正在收集新聞，請稍候...")
        print("   (這可能需要 1-3 分鐘，取決於新聞來源)")
        print()
    
    response = run_news_aggregator(
        preset_prompt=prompt,
        model=model,
        timeout=args.timeout,
        streaming=use_streaming,
        ccs_profile=settings.ccs_profile,
    )
    
    if not response.success:
        print(f"❌ Failed to collect news: {response.error}")
        return 1  # Critical failure - stop here
    
    news_content = response.content
    if not news_content or len(news_content.strip()) < 50:
        print("❌ Error: Claude returned insufficient news content")
        print(f"   Content length: {len(news_content) if news_content else 0} chars")
        return 1
    
    # Count news items for display
    news_count = count_news_items(news_content)
    print(f"✅ 成功收集 {news_count} 則新聞 ({len(news_content)} chars)")
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
        "news_count": news_count,
        "file_saved": True,
        "telegram_sent": None,
        "telegram_count": 0,
        "github_pushed": None,
    }
    
    # =========================================
    # Step 4: Send to Telegram (non-blocking)
    # =========================================
    print("-" * 40)
    print("Step 4: Sending to Telegram...")
    print("-" * 40)
    
    if args.dry_run or args.skip_telegram:
        print("⏭️  Skipped (--dry-run or --skip-telegram)")
        results["telegram_sent"] = "skipped"
        results["telegram_count"] = 0
    else:
        # Validate Telegram config
        tg_valid, tg_error = settings.validate_telegram()
        if not tg_valid:
            print(f"⏭️  Skipped: {tg_error}")
            print("   To enable: Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env")
            results["telegram_sent"] = "not_configured"
            results["telegram_count"] = 0
        else:
            try:
                print("   正在發送訊息到 Telegram...")
                # Pass GitHub info for the file link in summary message
                gh_repo = settings.github_repo if settings.validate_github()[0] else None
                tg_result = send_news_digest(
                    bot_token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id,
                    news_content=news_content,
                    date_str=date_str,
                    github_repo=gh_repo,
                    github_branch=settings.github_branch,
                )
                
                results["telegram_count"] = tg_result.messages_sent
                
                if tg_result.success:
                    print(f"✅ 已發送 {tg_result.messages_sent} 則訊息到 Telegram")
                    if tg_result.error:
                        print(f"   ⚠️  {tg_result.error}")
                    results["telegram_sent"] = True
                else:
                    print(f"⚠️  Telegram failed: {tg_result.error}")
                    results["telegram_sent"] = False
            except Exception as e:
                print(f"⚠️  Telegram error: {str(e)}")
                results["telegram_sent"] = False
                results["telegram_count"] = 0
    print()
    
    # =========================================
    # Step 5: Push to GitHub (non-blocking)
    # =========================================
    print("-" * 40)
    print("Step 5: Pushing to GitHub...")
    print("-" * 40)
    
    if args.dry_run or args.skip_github:
        print("⏭️  Skipped (--dry-run or --skip-github)")
        results["github_pushed"] = "skipped"
    else:
        # Validate GitHub config
        gh_valid, gh_error = settings.validate_github()
        if not gh_valid:
            print(f"⏭️  Skipped: {gh_error}")
            print("   To enable: Add GITHUB_TOKEN and GITHUB_REPO to .env")
            results["github_pushed"] = "not_configured"
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
    print("📊 執行摘要")
    print("=" * 60)
    print(f"  📰 新聞收集: ✅ ({results['news_count']} 則)")
    print(f"  💾 檔案儲存: ✅ ({file_path.name})")
    
    if results["telegram_sent"] == "skipped":
        print(f"  📱 Telegram: ⏭️  已跳過")
    elif results["telegram_sent"] == "not_configured":
        print(f"  📱 Telegram: ⏭️  未設定")
    elif results["telegram_sent"]:
        print(f"  📱 Telegram: ✅ 已發送 ({results['telegram_count']} 則訊息)")
    else:
        print(f"  📱 Telegram: ❌ 發送失敗")
    
    if results["github_pushed"] == "skipped":
        print(f"  🐙 GitHub: ⏭️  已跳過")
    elif results["github_pushed"] == "not_configured":
        print(f"  🐙 GitHub: ⏭️  未設定")
    elif results["github_pushed"]:
        print(f"  🐙 GitHub: ✅ 已推送")
    else:
        print(f"  🐙 GitHub: ❌ 推送失敗")
    
    print()
    print("=" * 60)
    print("✨ 每日新聞聚合完成！")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
