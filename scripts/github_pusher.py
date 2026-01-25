"""
GitHub Pusher for Daily News.
Handles committing and pushing news markdown files to GitHub.
"""

import subprocess
import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class GitResult:
    """Result of a Git operation."""
    success: bool
    message: str = ""
    error: str | None = None


def run_git_command(
    args: list[str],
    cwd: Path | None = None,
    timeout: int = 60,
) -> tuple[bool, str, str]:
    """
    Run a git command and return the result.
    
    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory
        timeout: Command timeout in seconds
        
    Returns:
        Tuple of (success, stdout, stderr)
    """
    cmd = ["git"] + args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        return (
            result.returncode == 0,
            result.stdout.strip(),
            result.stderr.strip(),
        )
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return False, "", str(e)


def configure_git_user(
    user_name: str,
    user_email: str,
    cwd: Path | None = None,
) -> GitResult:
    """
    Configure git user for commits (local to repo).
    
    Args:
        user_name: Git user name
        user_email: Git user email
        cwd: Repository directory
        
    Returns:
        GitResult with status
    """
    # Set user name
    success, _, err = run_git_command(
        ["config", "user.name", user_name],
        cwd=cwd,
    )
    if not success:
        return GitResult(success=False, error=f"Failed to set user.name: {err}")
    
    # Set user email
    success, _, err = run_git_command(
        ["config", "user.email", user_email],
        cwd=cwd,
    )
    if not success:
        return GitResult(success=False, error=f"Failed to set user.email: {err}")
    
    return GitResult(success=True, message="Git user configured")


def setup_remote_with_token(
    repo: str,
    token: str,
    cwd: Path,
    remote_name: str = "origin",
) -> GitResult:
    """
    Set up or update the remote URL with authentication token.
    
    Args:
        repo: Repository in format 'username/repo'
        token: GitHub Personal Access Token
        cwd: Repository directory
        remote_name: Name of the remote (default: origin)
        
    Returns:
        GitResult with status
    """
    # Build authenticated URL
    auth_url = f"https://{token}@github.com/{repo}.git"
    
    # Check if remote exists
    success, stdout, _ = run_git_command(["remote", "-v"], cwd=cwd)
    
    if remote_name in stdout:
        # Update existing remote
        success, _, err = run_git_command(
            ["remote", "set-url", remote_name, auth_url],
            cwd=cwd,
        )
    else:
        # Add new remote
        success, _, err = run_git_command(
            ["remote", "add", remote_name, auth_url],
            cwd=cwd,
        )
    
    if not success:
        return GitResult(success=False, error=f"Failed to configure remote: {err}")
    
    return GitResult(success=True, message="Remote configured with token")


def add_and_commit(
    file_path: Path,
    commit_message: str,
    cwd: Path,
) -> GitResult:
    """
    Stage a file and create a commit.
    
    Args:
        file_path: Path to the file to commit (relative to cwd)
        commit_message: Commit message
        cwd: Repository directory
        
    Returns:
        GitResult with status
    """
    # Make path relative if absolute
    if file_path.is_absolute():
        try:
            file_path = file_path.relative_to(cwd)
        except ValueError:
            return GitResult(
                success=False,
                error=f"File {file_path} is not within repository {cwd}",
            )
    
    # Stage the file
    success, _, err = run_git_command(["add", str(file_path)], cwd=cwd)
    if not success:
        return GitResult(success=False, error=f"Failed to stage file: {err}")
    
    # Check if there are changes to commit
    success, stdout, _ = run_git_command(["status", "--porcelain"], cwd=cwd)
    if not stdout.strip():
        return GitResult(
            success=True,
            message="No changes to commit (file already up to date)",
        )
    
    # Create commit
    success, stdout, err = run_git_command(
        ["commit", "-m", commit_message],
        cwd=cwd,
    )
    if not success:
        # Check if it's just "nothing to commit"
        if "nothing to commit" in err or "nothing to commit" in stdout:
            return GitResult(success=True, message="No changes to commit")
        return GitResult(success=False, error=f"Failed to commit: {err}")
    
    return GitResult(success=True, message="Changes committed successfully")


def push_to_remote(
    branch: str,
    cwd: Path,
    remote_name: str = "origin",
    timeout: int = 120,
) -> GitResult:
    """
    Push commits to remote repository.
    
    Args:
        branch: Branch name to push
        cwd: Repository directory
        remote_name: Name of the remote
        timeout: Push timeout in seconds
        
    Returns:
        GitResult with status
    """
    success, stdout, err = run_git_command(
        ["push", remote_name, branch],
        cwd=cwd,
        timeout=timeout,
    )
    
    if not success:
        # Check for common errors
        if "non-fast-forward" in err:
            return GitResult(
                success=False,
                error="Push rejected: remote has changes. Pull first or use --force (not recommended).",
            )
        return GitResult(success=False, error=f"Push failed: {err}")
    
    return GitResult(success=True, message="Pushed to remote successfully")


def push_news_file(
    file_path: Path,
    date_str: str,
    repo: str,
    token: str,
    branch: str,
    user_name: str,
    user_email: str,
    cwd: Path,
) -> GitResult:
    """
    Complete workflow to push a news file to GitHub.
    
    Args:
        file_path: Path to the news markdown file
        date_str: Date string for commit message
        repo: GitHub repository (username/repo)
        token: GitHub PAT
        branch: Branch to push to
        user_name: Git user name
        user_email: Git user email
        cwd: Repository root directory
        
    Returns:
        GitResult with overall status
    """
    print(f"[GitHub] Pushing {file_path.name} to {repo}...")
    
    # Step 1: Configure git user
    result = configure_git_user(user_name, user_email, cwd)
    if not result.success:
        return result
    
    # Step 2: Setup remote with token
    result = setup_remote_with_token(repo, token, cwd)
    if not result.success:
        return result
    
    # Step 3: Add and commit
    commit_message = f"📰 Daily News Update: {date_str}"
    result = add_and_commit(file_path, commit_message, cwd)
    if not result.success:
        return result
    
    # If no changes were made, we're done
    if "No changes" in result.message:
        print(f"[GitHub] {result.message}")
        return GitResult(success=True, message=result.message)
    
    # Step 4: Push to remote
    result = push_to_remote(branch, cwd)
    if not result.success:
        return result
    
    print(f"[GitHub] Successfully pushed {file_path.name}")
    return GitResult(
        success=True,
        message=f"Successfully pushed {file_path.name} to {repo}",
    )


if __name__ == "__main__":
    print("GitHub pusher module loaded successfully.")
    print("Use push_news_file() to push news to GitHub.")
