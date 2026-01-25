"""
Claude Code CLI Runner.
Wrapper for invoking Claude Code in non-interactive mode with proper permissions.
"""

import subprocess
import json
import shutil
from dataclasses import dataclass


@dataclass
class ClaudeResponse:
    """Response from Claude Code CLI."""
    success: bool
    content: str
    session_id: str | None = None
    error: str | None = None
    raw_output: str | None = None


# Tools that the news-aggregator-skill needs
ALLOWED_TOOLS = [
    "Read",
    "Write", 
    "Bash",
    "mcp__fetch__fetch",  # For web fetching
]


def build_command(
    prompt: str,
    model: str = "sonnet",
    output_format: str = "json",
    allowed_tools: list[str] | None = None,
    continue_session: bool = False,
    session_id: str | None = None,
) -> list[str]:
    """
    Build the Claude CLI command with appropriate flags.
    
    Args:
        prompt: The prompt to send to Claude
        model: Model to use (sonnet, opus, haiku, or full model ID)
        output_format: Output format (text, json, stream-json)
        allowed_tools: List of tools to auto-approve
        continue_session: Whether to continue the last session
        session_id: Specific session ID to resume
        
    Returns:
        List of command arguments
    """
    cmd = ["claude", "-p", prompt]
    
    # Add model flag
    cmd.extend(["--model", model])
    
    # Add output format
    cmd.extend(["--output-format", output_format])
    
    # Add allowed tools for auto-approval
    tools = allowed_tools or ALLOWED_TOOLS
    if tools:
        tools_str = ",".join(tools)
        cmd.extend(["--allowedTools", tools_str])
    
    # Handle session continuation
    if session_id:
        cmd.extend(["--resume", session_id])
    elif continue_session:
        cmd.append("--continue")
    
    return cmd


def run_claude(
    prompt: str,
    model: str = "sonnet",
    timeout: int = 300,
    allowed_tools: list[str] | None = None,
    continue_session: bool = False,
    session_id: str | None = None,
) -> ClaudeResponse:
    """
    Run Claude Code CLI with the given prompt.
    
    Args:
        prompt: The prompt to send to Claude
        model: Model to use (default: sonnet)
        timeout: Command timeout in seconds (default: 5 minutes)
        allowed_tools: List of tools to auto-approve
        continue_session: Whether to continue the last session
        session_id: Specific session ID to resume
        
    Returns:
        ClaudeResponse with the result
    """
    # Check if claude CLI is available
    if not shutil.which("claude"):
        return ClaudeResponse(
            success=False,
            content="",
            error="Claude CLI not found. Please install Claude Code first.",
        )
    
    cmd = build_command(
        prompt=prompt,
        model=model,
        output_format="json",
        allowed_tools=allowed_tools,
        continue_session=continue_session,
        session_id=session_id,
    )
    
    print(f"[ClaudeRunner] Executing: {' '.join(cmd[:5])}...")  # Only show first 5 args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        raw_output = result.stdout
        
        # Try to parse JSON response
        if raw_output.strip():
            try:
                response_data = json.loads(raw_output)
                
                # Extract content from JSON response
                content = response_data.get("result", "")
                session_id = response_data.get("session_id")
                
                # Check for errors in response
                if response_data.get("is_error"):
                    return ClaudeResponse(
                        success=False,
                        content="",
                        error=content or "Claude returned an error",
                        session_id=session_id,
                        raw_output=raw_output,
                    )
                
                return ClaudeResponse(
                    success=True,
                    content=content,
                    session_id=session_id,
                    raw_output=raw_output,
                )
                
            except json.JSONDecodeError:
                # If JSON parsing fails, treat raw output as content
                if result.returncode == 0:
                    return ClaudeResponse(
                        success=True,
                        content=raw_output,
                        raw_output=raw_output,
                    )
                else:
                    return ClaudeResponse(
                        success=False,
                        content="",
                        error=result.stderr or raw_output,
                        raw_output=raw_output,
                    )
        
        # Empty output
        if result.returncode != 0:
            return ClaudeResponse(
                success=False,
                content="",
                error=result.stderr or "Claude returned empty output with error code",
            )
        
        return ClaudeResponse(
            success=False,
            content="",
            error="Claude returned empty output",
        )
        
    except subprocess.TimeoutExpired:
        return ClaudeResponse(
            success=False,
            content="",
            error=f"Claude command timed out after {timeout} seconds",
        )
    except Exception as e:
        return ClaudeResponse(
            success=False,
            content="",
            error=f"Unexpected error running Claude: {str(e)}",
        )


def run_news_aggregator(
    preset_prompt: str,
    model: str = "sonnet",
    timeout: int = 300,
) -> ClaudeResponse:
    """
    Run the news aggregator skill with the given preset prompt.
    
    Args:
        preset_prompt: The preset prompt to trigger news aggregation
        model: Model to use
        timeout: Command timeout in seconds
        
    Returns:
        ClaudeResponse with news content
    """
    return run_claude(
        prompt=preset_prompt,
        model=model,
        timeout=timeout,
    )


if __name__ == "__main__":
    # Test the Claude runner
    print("Testing Claude runner...")
    response = run_claude("Say hello in one sentence.", model="sonnet", timeout=60)
    print(f"Success: {response.success}")
    print(f"Content: {response.content[:200] if response.content else 'None'}...")
    if response.error:
        print(f"Error: {response.error}")
