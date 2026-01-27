"""
Telegram Sender for Daily News.
Handles sending formatted news messages to a Telegram channel/chat.
Splits overview and individual news items into separate messages.
Uses telegramify-markdown for proper MarkdownV2 formatting.
"""

import re
import time
import requests
from dataclasses import dataclass

import telegramify_markdown
from telegramify_markdown.customize import get_runtime_config

# Configure telegramify-markdown
_config = get_runtime_config()
_config.markdown_symbol.head_level_1 = "📌"
_config.markdown_symbol.head_level_2 = "📋"
_config.markdown_symbol.head_level_3 = "▪️"
_config.markdown_symbol.link = "🔗"
_config.strict_markdown = False  # Allow __underline__ as underline


@dataclass
class TelegramResult:
    """Result of a Telegram send operation."""
    success: bool
    message_id: int | None = None
    messages_sent: int = 0
    error: str | None = None


# Telegram message limits
MAX_MESSAGE_LENGTH = 4096

# Delay between messages to avoid rate limiting (in seconds)
MESSAGE_DELAY = 0.5


def convert_markdown_to_telegram(text: str) -> str:
    """
    Convert standard Markdown to Telegram MarkdownV2 format.
    
    Args:
        text: Standard markdown text
        
    Returns:
        Telegram MarkdownV2 formatted text
    """
    try:
        return telegramify_markdown.markdownify(
            text,
            max_line_length=None,
            normalize_whitespace=False,
        )
    except Exception as e:
        print(f"   [Warning] Markdown conversion failed: {e}, using original text")
        return text


def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "MarkdownV2",
    disable_web_page_preview: bool = True,
) -> TelegramResult:
    """
    Send a message to Telegram.
    
    Args:
        bot_token: Telegram Bot API token
        chat_id: Target chat/channel ID
        text: Message text to send
        parse_mode: Parse mode (MarkdownV2, HTML, or empty)
        disable_web_page_preview: Whether to disable link previews
        
    Returns:
        TelegramResult with success status
    """
    if not bot_token or not chat_id:
        return TelegramResult(
            success=False,
            error="Bot token or chat ID not provided",
        )
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    
    if parse_mode:
        payload["parse_mode"] = parse_mode
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response_data = response.json()
        
        if response_data.get("ok"):
            message_id = response_data.get("result", {}).get("message_id")
            return TelegramResult(success=True, message_id=message_id, messages_sent=1)
        else:
            error_desc = response_data.get("description", "Unknown error")
            # If MarkdownV2 parsing fails, try without parse_mode
            if "can't parse" in error_desc.lower() and parse_mode:
                print(f"   [Warning] {parse_mode} parsing failed, retrying without formatting...")
                return send_message(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    text=text,
                    parse_mode="",  # No parse mode
                    disable_web_page_preview=disable_web_page_preview,
                )
            return TelegramResult(success=False, error=error_desc)
            
    except requests.exceptions.Timeout:
        return TelegramResult(success=False, error="Request timed out")
    except requests.exceptions.RequestException as e:
        return TelegramResult(success=False, error=f"Request failed: {str(e)}")
    except Exception as e:
        return TelegramResult(success=False, error=f"Unexpected error: {str(e)}")


def truncate_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """
    Truncate a message to fit Telegram's limit, trying to cut at sentence boundaries.
    """
    if len(text) <= max_length:
        return text
    
    # Reserve space for truncation indicator
    max_len = max_length - 20
    
    # Try to cut at the last sentence boundary
    truncated = text[:max_len]
    
    # Find last sentence end
    for end_char in ["。", ".", "！", "!", "？", "?"]:
        last_idx = truncated.rfind(end_char)
        if last_idx > max_len // 2:  # Only if it's past halfway
            return truncated[:last_idx + 1] + "\n\n⋯ \\(訊息過長，已截斷\\)"
    
    # Find last newline
    last_newline = truncated.rfind("\n")
    if last_newline > max_len // 2:
        return truncated[:last_newline] + "\n\n⋯ \\(訊息過長，已截斷\\)"
    
    return truncated + "\n\n⋯ \\(訊息過長，已截斷\\)"


def parse_news_content(content: str) -> tuple[str, list[str]]:
    """
    Parse news content into overview and individual news items.
    
    The overview includes:
    - The intro text before the summary section
    - The full summary section (總覽) with keywords, insights, and statistics
    
    News items are the individual news articles separated by ---.
    
    Args:
        content: The full news content in Markdown
        
    Returns:
        Tuple of (overview_text, list_of_news_items)
    """
    # Remove file header added by save_news_to_file
    # Pattern: # Daily News - YYYY-MM-DD\n\n> Generated on YYYY-MM-DD HH:MM:SS\n\n---
    content = re.sub(
        r'^# Daily News - \d{4}-\d{2}-\d{2}\s*\n+>\s*Generated on[^\n]*\n+---\n*',
        '',
        content,
        flags=re.MULTILINE
    )
    
    # Split by --- separator
    sections = re.split(r'\n---+\n', content)
    
    # Filter out empty sections
    sections = [s.strip() for s in sections if s.strip()]
    
    # Filter out common non-news sections
    sections = [s for s in sections if not s.startswith("完整的報告已保存") and not s.startswith("完整報告已保存")]
    
    if len(sections) <= 1:
        # No separator found, try to split by numbered headers
        news_pattern = r'(?=(?:^|\n)(?:#{1,3}\s*)?\d+[\.\)、])'
        parts = re.split(news_pattern, content)
        
        if len(parts) > 1:
            overview = parts[0].strip()
            news_items = [p.strip() for p in parts[1:] if p.strip()]
            return overview, news_items
        
        # Fallback: return whole content as overview
        return content.strip(), []
    
    # Identify the overview section(s) vs news items
    # News items typically have:
    # - ### Title format (H3 heading)
    # - 來源 or 來源平台 or 來源：
    # - 🔗 連結 or 連結：
    overview_parts = []
    news_items = []
    in_news_section = False
    
    for section in sections:
        # Check if this section is a news item
        # Multiple patterns to detect news items:
        is_news_item = _is_news_item(section)
        
        if is_news_item:
            in_news_section = True
            news_items.append(section)
        elif in_news_section:
            # Once we're in news section, everything else is a news item
            news_items.append(section)
        else:
            # Still in overview section
            overview_parts.append(section)
    
    # Join overview parts with proper formatting (no --- separators in the message)
    overview = "\n\n".join(overview_parts) if overview_parts else ""
    
    return overview, news_items


def _is_news_item(section: str) -> bool:
    """
    Check if a section is a news item based on common patterns.
    
    Args:
        section: A section of text to check
        
    Returns:
        True if the section appears to be a news item
    """
    # Pattern 1: Starts with # followed by number (e.g., "# 1.", "# 2.")
    starts_with_numbered_h1 = bool(re.match(r'^#\s*\d+[\.\)、]', section))
    
    # Pattern 2: Starts with ### (H3 heading) - common for news titles
    starts_with_h3 = section.startswith("###")
    
    # Pattern 3: Starts with ** (bold text) - old format
    starts_with_bold = section.startswith("**")
    
    # Pattern 4: Contains source indicators
    has_source = any(indicator in section for indicator in [
        "來源：", "來源:", "來源平台", "**來源:**", "**來源：**",
        "**來源平台**", "Hacker News", "GitHub Trending", "Product Hunt",
    ])
    
    # Pattern 5: Contains link indicators
    has_link = "🔗" in section or "連結：" in section or "連結:" in section
    
    # Pattern 6: Contains "熱度" (popularity/points)
    has_popularity = "熱度" in section or "points" in section
    
    # Pattern 7: Contains thinking question indicator
    has_thinking = "思考問題" in section or "**思考問題**" in section
    
    # Pattern 8: Contains summary indicator
    has_summary = "重點摘要" in section or "**重點摘要**" in section
    
    # A section is a news item if it:
    # - Starts with numbered H1 (# 1., # 2., etc.)
    # - OR starts with H3 or bold AND has source/link/popularity indicators
    # - OR has both source AND link indicators (regardless of heading)
    # - OR has source AND (thinking question OR summary)
    if starts_with_numbered_h1:
        return True
    
    if (starts_with_h3 or starts_with_bold) and (has_source or has_link or has_popularity):
        return True
    
    if has_source and has_link:
        return True
    
    if has_source and (has_thinking or has_summary):
        return True
    
    return False


def build_github_file_url(repo: str, branch: str, file_path: str) -> str:
    """
    Build the GitHub URL for a news file.
    
    Args:
        repo: GitHub repository (username/repo)
        branch: Branch name
        file_path: Relative path to the file (e.g., news/2026-01-26.md)
        
    Returns:
        Full GitHub URL to the file
    """
    return f"https://github.com/{repo}/blob/{branch}/{file_path}"


def format_overview_message(
    overview: str,
    date_str: str,
    github_url: str | None = None,
) -> str:
    """Format the overview section as a Telegram message."""
    header = f"🗞️ **每日新聞總覽 - {date_str}**\n\n"
    content = header + overview
    
    # Add GitHub link at the bottom if provided
    if github_url:
        content += f"\n\n---\n\n📎 [完整報告]({github_url})"
    
    return content


def format_news_item_message(item: str, index: int, total: int) -> str:
    """Format a single news item as a Telegram message."""
    header = f"📰 **新聞 {index}/{total}**\n\n"
    return header + item


def send_news_digest(
    bot_token: str,
    chat_id: str,
    news_content: str,
    date_str: str,
    github_repo: str | None = None,
    github_branch: str = "main",
    progress_callback: callable = None,
) -> TelegramResult:
    """
    Send a formatted news digest to Telegram as multiple messages.
    
    Sends:
    1. Overview message first (includes summary + GitHub link)
    2. Each news item as a separate message
    
    Args:
        bot_token: Telegram Bot API token
        chat_id: Target chat/channel ID
        news_content: The news content in Markdown
        date_str: Date string for the header
        github_repo: Optional GitHub repo for file link (username/repo)
        github_branch: GitHub branch name (default: main)
        progress_callback: Optional callback(current, total) for progress updates
        
    Returns:
        TelegramResult with overall status
    """
    # Parse content into overview and news items
    overview, news_items = parse_news_content(news_content)
    
    total_messages = 1 + len(news_items)  # 1 for overview
    messages_sent = 0
    first_message_id = None
    errors = []
    
    # Build GitHub URL if repo is provided
    github_url = None
    if github_repo:
        file_path = f"news/{date_str}.md"
        github_url = build_github_file_url(github_repo, github_branch, file_path)
    
    # Send overview first
    if progress_callback:
        progress_callback(1, total_messages, "總覽")
    
    overview_msg = format_overview_message(overview, date_str, github_url)
    # Convert to Telegram MarkdownV2 format
    overview_msg_converted = convert_markdown_to_telegram(overview_msg)
    overview_msg_converted = truncate_message(overview_msg_converted)
    
    result = send_message(bot_token, chat_id, overview_msg_converted)
    if result.success:
        messages_sent += 1
        first_message_id = result.message_id
        print(f"   [1/{total_messages}] ✅ 已發送總覽")
    else:
        errors.append(f"Overview: {result.error}")
        print(f"   [1/{total_messages}] ❌ 總覽發送失敗: {result.error}")
    
    # Send each news item
    for i, item in enumerate(news_items, start=1):
        # Rate limiting delay
        time.sleep(MESSAGE_DELAY)
        
        msg_num = i + 1  # +1 because overview is message 1
        
        if progress_callback:
            progress_callback(msg_num, total_messages, f"新聞 {i}")
        
        item_msg = format_news_item_message(item, i, len(news_items))
        # Convert to Telegram MarkdownV2 format
        item_msg_converted = convert_markdown_to_telegram(item_msg)
        item_msg_converted = truncate_message(item_msg_converted)
        
        result = send_message(bot_token, chat_id, item_msg_converted)
        if result.success:
            messages_sent += 1
            print(f"   [{msg_num}/{total_messages}] ✅ 已發送新聞 {i}")
            if first_message_id is None:
                first_message_id = result.message_id
        else:
            errors.append(f"News {i}: {result.error}")
            print(f"   [{msg_num}/{total_messages}] ❌ 新聞 {i} 發送失敗: {result.error}")
    
    # If no items were parsed, send as single long message
    if not news_items:
        print("   [Info] 未能解析新聞項目，以單一訊息發送...")
        full_msg = format_overview_message(news_content, date_str, github_url)
        full_msg_converted = convert_markdown_to_telegram(full_msg)
        full_msg_converted = truncate_message(full_msg_converted)
        
        result = send_message(bot_token, chat_id, full_msg_converted)
        if result.success:
            return TelegramResult(
                success=True,
                message_id=result.message_id,
                messages_sent=1,
            )
        else:
            return TelegramResult(
                success=False,
                error=result.error,
            )
    
    # Return overall result
    if messages_sent == 0:
        return TelegramResult(
            success=False,
            error="; ".join(errors) if errors else "No messages sent",
        )
    
    # Partial success is still considered success
    return TelegramResult(
        success=True,
        message_id=first_message_id,
        messages_sent=messages_sent,
        error=f"{len(errors)} 則訊息發送失敗" if errors else None,
    )


if __name__ == "__main__":
    # Test (requires actual credentials)
    print("Telegram sender module loaded successfully.")
    print("Use send_news_digest() to send formatted news.")
