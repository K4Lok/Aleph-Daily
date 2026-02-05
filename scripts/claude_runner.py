"""
CCS CLI Runner.
Wrapper for invoking CCS (Claude Code Switch) in non-interactive mode with proper permissions.
Supports streaming output for real-time progress display.
"""

import subprocess
import json
import shutil
import sys
import threading
import time
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
    verbose: bool = False,
    ccs_profile: str = "glm",
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
        verbose: Whether to enable verbose output (required for stream-json with -p)
        ccs_profile: CCS profile to use (default: "glm" for GLM LLM)

    Returns:
        List of command arguments
    """
    cmd = ["ccs", ccs_profile, "-p", prompt]
    
    # Add model flag
    cmd.extend(["--model", model])
    
    # Add output format
    cmd.extend(["--output-format", output_format])
    
    # Add verbose flag if needed (required for stream-json with -p)
    if verbose or output_format == "stream-json":
        cmd.append("--verbose")
    
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
    ccs_profile: str = "glm",
) -> ClaudeResponse:
    """
    Run Claude Code CLI with the given prompt (non-streaming).

    Args:
        prompt: The prompt to send to Claude
        model: Model to use (default: sonnet)
        timeout: Command timeout in seconds (default: 5 minutes)
        allowed_tools: List of tools to auto-approve
        continue_session: Whether to continue the last session
        session_id: Specific session ID to resume
        ccs_profile: CCS profile to use (default: "glm")

    Returns:
        ClaudeResponse with the result
    """
    # Check if ccs CLI is available
    if not shutil.which("ccs"):
        return ClaudeResponse(
            success=False,
            content="",
            error="CCS CLI not found. Please install CCS first: npm install -g @kaitranntt/ccs",
        )
    
    cmd = build_command(
        prompt=prompt,
        model=model,
        output_format="json",
        allowed_tools=allowed_tools,
        continue_session=continue_session,
        session_id=session_id,
        ccs_profile=ccs_profile,
    )
    
    print(f"[CCSRunner] Executing: {' '.join(cmd[:5])}...")  # Only show first 5 args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,  # Prevent hanging on stdin
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
                        error=content or "CCS returned an error",
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
                error=result.stderr or "CCS returned empty output with error code",
            )
        
        return ClaudeResponse(
            success=False,
            content="",
            error="CCS returned empty output",
        )
        
    except subprocess.TimeoutExpired as e:
        # Try to capture any partial output
        partial_stdout = e.stdout if hasattr(e, 'stdout') and e.stdout else ""
        partial_stderr = e.stderr if hasattr(e, 'stderr') and e.stderr else ""
        error_msg = f"CCS command timed out after {timeout} seconds"
        if partial_stderr:
            error_msg += f"\nStderr: {partial_stderr[:500]}"
        return ClaudeResponse(
            success=False,
            content="",
            error=error_msg,
            raw_output=partial_stdout if partial_stdout else None,
        )
    except Exception as e:
        return ClaudeResponse(
            success=False,
            content="",
            error=f"Unexpected error running CCS: {str(e)}",
        )


def run_claude_streaming(
    prompt: str,
    model: str = "sonnet",
    timeout: int = 300,
    allowed_tools: list[str] | None = None,
    continue_session: bool = False,
    session_id: str | None = None,
    verbose: bool = True,
    ccs_profile: str = "glm",
) -> ClaudeResponse:
    """
    Run Claude Code CLI with streaming output for real-time progress display.

    Args:
        prompt: The prompt to send to Claude
        model: Model to use (default: sonnet)
        timeout: Command timeout in seconds (default: 5 minutes)
        allowed_tools: List of tools to auto-approve
        continue_session: Whether to continue the last session
        session_id: Specific session ID to resume
        verbose: Whether to print streaming output (default: True)
        ccs_profile: CCS profile to use (default: "glm")

    Returns:
        ClaudeResponse with the result
    """
    # Check if ccs CLI is available
    if not shutil.which("ccs"):
        return ClaudeResponse(
            success=False,
            content="",
            error="CCS CLI not found. Please install CCS first: npm install -g @kaitranntt/ccs",
        )
    
    cmd = build_command(
        prompt=prompt,
        model=model,
        output_format="stream-json",  # Use streaming JSON format
        allowed_tools=allowed_tools,
        continue_session=continue_session,
        session_id=session_id,
        ccs_profile=ccs_profile,
    )
    
    print(f"[CCSRunner] Executing with streaming: {' '.join(cmd[:5])}...")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,  # Line buffered
        )
        
        collected_content = []
        result_content = ""
        result_session_id = None
        is_error = False
        last_activity = time.time()
        
        # Track what we've seen for progress display
        current_tool = None
        tool_count = 0
        
        def read_stderr():
            """Read stderr in a separate thread to prevent blocking."""
            nonlocal is_error
            for line in process.stderr:
                if line.strip():
                    print(f"   [stderr] {line.strip()}", file=sys.stderr)
        
        # Start stderr reader thread
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()
        
        # Process stdout line by line
        while True:
            # Check timeout
            if time.time() - last_activity > timeout:
                process.kill()
                return ClaudeResponse(
                    success=False,
                    content="",
                    error=f"CCS command timed out after {timeout} seconds of inactivity",
                )
            
            # Read a line with a short timeout
            try:
                line = process.stdout.readline()
            except Exception:
                break
            
            if not line:
                # Check if process has finished
                if process.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            
            last_activity = time.time()
            line = line.strip()
            
            if not line:
                continue
            
            # Parse the streaming JSON
            try:
                event = json.loads(line)
                event_type = event.get("type", "")
                
                if event_type == "assistant":
                    # Assistant message - contains the actual response
                    message = event.get("message", {})
                    content_blocks = message.get("content", [])
                    for block in content_blocks:
                        if block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                collected_content.append(text)
                
                elif event_type == "content_block_delta":
                    # Streaming text delta
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text and verbose:
                            # Print streaming text (partial)
                            print(text, end="", flush=True)
                            collected_content.append(text)
                
                elif event_type == "result":
                    # Final result
                    result_content = event.get("result", "")
                    result_session_id = event.get("session_id")
                    is_error = event.get("is_error", False)
                    if verbose:
                        print()  # Newline after streaming
                
                elif event_type == "tool_use" or event_type == "tool_use_begin":
                    # Tool being used
                    tool_name = event.get("name", event.get("tool", "unknown"))
                    tool_count += 1
                    if verbose and tool_name != current_tool:
                        current_tool = tool_name
                        print(f"\n   🔧 [{tool_count}] Using tool: {tool_name}", flush=True)
                
                elif event_type == "tool_result":
                    # Tool result
                    if verbose:
                        result_preview = str(event.get("result", ""))[:100]
                        if len(str(event.get("result", ""))) > 100:
                            result_preview += "..."
                        print(f"   ✓ Tool completed", flush=True)
                
                elif event_type == "error":
                    # Error event
                    error_msg = event.get("error", {}).get("message", "Unknown error")
                    is_error = True
                    if verbose:
                        print(f"\n   ❌ Error: {error_msg}", file=sys.stderr, flush=True)
                    return ClaudeResponse(
                        success=False,
                        content="",
                        error=error_msg,
                    )
                
            except json.JSONDecodeError:
                # Not JSON, might be raw output
                if verbose:
                    print(f"   [raw] {line[:100]}", flush=True)
        
        # Wait for process to complete
        process.wait()
        
        # Use result content if available, otherwise join collected content
        final_content = result_content if result_content else "".join(collected_content)
        
        if is_error:
            return ClaudeResponse(
                success=False,
                content="",
                error=final_content or "Claude returned an error",
                session_id=result_session_id,
            )
        
        if final_content:
            return ClaudeResponse(
                success=True,
                content=final_content,
                session_id=result_session_id,
            )
        
        return ClaudeResponse(
            success=False,
            content="",
            error="CCS returned empty output",
        )
        
    except Exception as e:
        return ClaudeResponse(
            success=False,
            content="",
            error=f"Unexpected error running CCS: {str(e)}",
        )


def run_news_aggregator(
    preset_prompt: str,
    model: str = "sonnet",
    timeout: int = 300,
    streaming: bool = True,
    ccs_profile: str = "glm",
) -> ClaudeResponse:
    """
    Run the news aggregator skill with the given preset prompt.

    Args:
        preset_prompt: The preset prompt to trigger news aggregation
        model: Model to use
        timeout: Command timeout in seconds
        streaming: Whether to use streaming output (default: True)
        ccs_profile: CCS profile to use (default: "glm")

    Returns:
        ClaudeResponse with news content
    """
    if streaming:
        return run_claude_streaming(
            prompt=preset_prompt,
            model=model,
            timeout=timeout,
            verbose=True,
            ccs_profile=ccs_profile,
        )
    else:
        return run_claude(
            prompt=preset_prompt,
            model=model,
            timeout=timeout,
            ccs_profile=ccs_profile,
        )


if __name__ == "__main__":
    # Test the CCS runner
    print("Testing CCS runner with streaming...")
    response = run_claude_streaming("Say hello in one sentence.", model="sonnet", timeout=60)
    print(f"\nSuccess: {response.success}")
    print(f"Content: {response.content[:200] if response.content else 'None'}...")
    if response.error:
        print(f"Error: {response.error}")
