"""
Telegram Sender for Daily News.
Handles sending formatted news messages to a Telegram channel/chat.
Splits overview and individual news items into separate messages.
"""

import re
import time
import requests
from dataclasses import dataclass


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


def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "Markdown",
    disable_web_page_preview: bool = True,
) -> TelegramResult:
    """
    Send a message to Telegram.
    
    Args:
        bot_token: Telegram Bot API token
        chat_id: Target chat/channel ID
        text: Message text to send
        parse_mode: Parse mode (Markdown, HTML, or empty)
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
            # If Markdown parsing fails, try without parse_mode
            if "can't parse" in error_desc.lower() and parse_mode:
                print("[Telegram] Markdown parsing failed, retrying without formatting...")
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
            return truncated[:last_idx + 1] + "\n\n⋯ (訊息過長，已截斷)"
    
    # Find last newline
    last_newline = truncated.rfind("\n")
    if last_newline > max_len // 2:
        return truncated[:last_newline] + "\n\n⋯ (訊息過長，已截斷)"
    
    return truncated + "\n\n⋯ (訊息過長，已截斷)"


def parse_news_content(content: str) -> tuple[str, list[str]]:
    """
    Parse news content into overview and individual news items.
    
    Args:
        content: The full news content in Markdown
        
    Returns:
        Tuple of (overview_text, list_of_news_items)
    """
    # Split by --- separator
    sections = re.split(r'\n---+\n', content)
    
    if len(sections) <= 1:
        # No separator found, try to split by numbered headers
        # Look for patterns like "### 1.", "## 1.", "1.", etc.
        news_pattern = r'(?=(?:^|\n)(?:#{1,3}\s*)?\d+[\.\)、])'
        parts = re.split(news_pattern, content)
        
        if len(parts) > 1:
            overview = parts[0].strip()
            news_items = [p.strip() for p in parts[1:] if p.strip()]
            return overview, news_items
        
        # Fallback: return whole content as overview
        return content.strip(), []
    
    # First section is usually overview/header
    overview = sections[0].strip()
    
    # Rest are news items
    news_items = [s.strip() for s in sections[1:] if s.strip()]
    
    return overview, news_items


def format_overview_message(overview: str, date_str: str) -> str:
    """Format the overview section as a Telegram message."""
    header = f"🗞️ *每日新聞總覽 - {date_str}*\n\n"
    return header + overview


def format_news_item_message(item: str, index: int, total: int) -> str:
    """Format a single news item as a Telegram message."""
    header = f"📰 *新聞 {index}/{total}*\n\n"
    return header + item


def send_news_digest(
    bot_token: str,
    chat_id: str,
    news_content: str,
    date_str: str,
    progress_callback: callable = None,
) -> TelegramResult:
    """
    Send a formatted news digest to Telegram as multiple messages.
    
    Sends:
    1. Overview message first
    2. Each news item as a separate message
    
    Args:
        bot_token: Telegram Bot API token
        chat_id: Target chat/channel ID
        news_content: The news content in Markdown
        date_str: Date string for the header
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
    
    # Send overview first
    if progress_callback:
        progress_callback(1, total_messages, "總覽")
    
    overview_msg = format_overview_message(overview, date_str)
    overview_msg = truncate_message(overview_msg)
    
    result = send_message(bot_token, chat_id, overview_msg)
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
        item_msg = truncate_message(item_msg)
        
        result = send_message(bot_token, chat_id, item_msg)
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
        full_msg = format_overview_message(news_content, date_str)
        full_msg = truncate_message(full_msg)
        
        result = send_message(bot_token, chat_id, full_msg)
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
