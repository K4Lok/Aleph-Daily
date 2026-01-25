"""
Telegram Sender for Daily News.
Handles sending formatted news messages to a Telegram channel/chat.
"""

import requests
from dataclasses import dataclass


@dataclass
class TelegramResult:
    """Result of a Telegram send operation."""
    success: bool
    message_id: int | None = None
    error: str | None = None


# Telegram message limits
MAX_MESSAGE_LENGTH = 4096


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
            return TelegramResult(success=True, message_id=message_id)
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


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """
    Split a long message into chunks that fit Telegram's limit.
    Tries to split at newlines for cleaner breaks.
    
    Args:
        text: The text to split
        max_length: Maximum length per chunk
        
    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by lines first
    lines = text.split("\n")
    
    for line in lines:
        # If adding this line would exceed limit
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # If single line is too long, split it by words
            if len(line) > max_length:
                words = line.split(" ")
                for word in words:
                    if len(current_chunk) + len(word) + 1 > max_length:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = word + " "
                    else:
                        current_chunk += word + " "
            else:
                current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


def send_long_message(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "Markdown",
) -> list[TelegramResult]:
    """
    Send a long message, automatically splitting if needed.
    
    Args:
        bot_token: Telegram Bot API token
        chat_id: Target chat/channel ID
        text: Message text (can be longer than 4096 chars)
        parse_mode: Parse mode
        
    Returns:
        List of TelegramResult for each chunk sent
    """
    chunks = split_message(text)
    results = []
    
    for i, chunk in enumerate(chunks):
        # Add part indicator for multi-part messages
        if len(chunks) > 1:
            header = f"📰 Part {i + 1}/{len(chunks)}\n\n"
            chunk = header + chunk
        
        result = send_message(
            bot_token=bot_token,
            chat_id=chat_id,
            text=chunk,
            parse_mode=parse_mode,
        )
        results.append(result)
        
        # If one part fails, log but continue with others
        if not result.success:
            print(f"[Telegram] Failed to send part {i + 1}: {result.error}")
    
    return results


def send_news_digest(
    bot_token: str,
    chat_id: str,
    news_content: str,
    date_str: str,
) -> TelegramResult:
    """
    Send a formatted news digest to Telegram.
    
    Args:
        bot_token: Telegram Bot API token
        chat_id: Target chat/channel ID
        news_content: The news content in Markdown
        date_str: Date string for the header
        
    Returns:
        TelegramResult (uses first result if message was split)
    """
    # Add header
    header = f"🗞️ *Daily News Digest - {date_str}*\n\n"
    full_message = header + news_content
    
    # Add footer
    footer = "\n\n---\n_Generated by Daily News Aggregator_"
    full_message += footer
    
    results = send_long_message(
        bot_token=bot_token,
        chat_id=chat_id,
        text=full_message,
    )
    
    # Return overall success status
    if not results:
        return TelegramResult(success=False, error="No messages sent")
    
    # Consider it successful if at least the first part was sent
    all_success = all(r.success for r in results)
    first_result = results[0]
    
    if all_success:
        return TelegramResult(
            success=True,
            message_id=first_result.message_id,
        )
    else:
        failed_count = sum(1 for r in results if not r.success)
        return TelegramResult(
            success=first_result.success,
            message_id=first_result.message_id,
            error=f"{failed_count}/{len(results)} parts failed to send",
        )


if __name__ == "__main__":
    # Test (requires actual credentials)
    print("Telegram sender module loaded successfully.")
    print("Use send_news_digest() to send formatted news.")
