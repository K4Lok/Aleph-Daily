"""
Skill Manager for news-aggregator-skill.
Handles checking installation status and installing the skill if needed.
"""

import subprocess
import shutil
from pathlib import Path


SKILL_NAME = "news-aggregator-skill"
SKILL_REPO_URL = "https://github.com/cclank/news-aggregator-skill"
SKILL_GIT_URL = "https://github.com/cclank/news-aggregator-skill.git"

# Installation location
SKILLS_DIR = Path.home() / ".claude" / "skills"
SKILL_DIR = SKILLS_DIR / SKILL_NAME


def is_skill_installed() -> bool:
    """
    Check if news-aggregator-skill is installed.
    
    Returns:
        True if the skill is found in any known location.
    """
    # Check ~/.claude/skills/news-aggregator-skill/SKILL.md
    skill_md_path = SKILL_DIR / "SKILL.md"
    if skill_md_path.exists():
        return True
    
    # Check if the skill directory exists with any content
    if SKILL_DIR.exists():
        try:
            if any(SKILL_DIR.iterdir()):
                return True
        except PermissionError:
            pass
    
    return False


def install_skill_via_git() -> tuple[bool, str]:
    """
    Install skill by cloning the git repository directly.
    This is a fallback when npx skills has TTY issues.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    print(f"[SkillManager] Installing {SKILL_NAME} via git clone...")
    
    # Check if git is available
    if not shutil.which("git"):
        return False, "git is not installed. Please install git first."
    
    try:
        # Create skills directory if it doesn't exist
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Remove existing directory if it exists but is empty/broken
        if SKILL_DIR.exists():
            shutil.rmtree(SKILL_DIR)
        
        # Clone the repository
        result = subprocess.run(
            ["git", "clone", SKILL_GIT_URL, str(SKILL_DIR)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode == 0:
            # Verify SKILL.md exists
            if (SKILL_DIR / "SKILL.md").exists():
                print(f"[SkillManager] Successfully installed {SKILL_NAME} via git")
                return True, f"Successfully installed {SKILL_NAME}"
            else:
                return False, "Cloned but SKILL.md not found in repository"
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            return False, f"Git clone failed: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return False, "Git clone timed out after 2 minutes"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def install_skill_via_npx() -> tuple[bool, str]:
    """
    Install news-aggregator-skill using npx skills add.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    print(f"[SkillManager] Installing {SKILL_NAME} via npx...")
    
    # Check if npx is available
    if not shutil.which("npx"):
        return False, "npx is not installed"
    
    try:
        # Run npx skills add with --yes to auto-confirm
        result = subprocess.run(
            ["npx", "--yes", "skills", "add", SKILL_REPO_URL],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        # Check return code
        if result.returncode == 0:
            print(f"[SkillManager] Successfully installed {SKILL_NAME}")
            return True, f"Successfully installed {SKILL_NAME}"
        else:
            # Check for TTY error which is common in non-interactive mode
            output = result.stdout + result.stderr
            if "TTY" in output or "uv_tty_init" in output:
                return False, "npx skills has TTY issues in non-interactive mode"
            
            # Filter out npm warn lines from error message
            stderr_lines = result.stderr.split('\n') if result.stderr else []
            error_lines = [l for l in stderr_lines if not l.startswith('npm warn')]
            error_msg = '\n'.join(error_lines).strip() or "Unknown error"
            return False, error_msg
            
    except subprocess.TimeoutExpired:
        return False, "Timed out after 2 minutes"
    except FileNotFoundError:
        return False, "npx command not found"
    except Exception as e:
        return False, str(e)


def install_skill() -> tuple[bool, str]:
    """
    Install news-aggregator-skill, trying multiple methods.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    print(f"[SkillManager] Installing {SKILL_NAME}...")
    
    # Try npx first
    success, msg = install_skill_via_npx()
    if success:
        return True, msg
    
    print(f"[SkillManager] npx method failed: {msg}")
    print(f"[SkillManager] Trying git clone fallback...")
    
    # Fallback to git clone
    success, msg = install_skill_via_git()
    if success:
        return True, msg
    
    return False, f"All installation methods failed. Last error: {msg}"


def ensure_skill_installed() -> tuple[bool, str]:
    """
    Ensure the news-aggregator-skill is installed.
    If not installed, attempt to install it.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    if is_skill_installed():
        print(f"[SkillManager] {SKILL_NAME} is already installed")
        return True, f"{SKILL_NAME} is already installed"
    
    print(f"[SkillManager] {SKILL_NAME} not found, attempting installation...")
    return install_skill()


def get_skill_path() -> Path | None:
    """
    Get the path to the installed skill.
    
    Returns:
        Path to the skill directory, or None if not found.
    """
    if SKILL_DIR.exists():
        return SKILL_DIR
    return None


if __name__ == "__main__":
    # Test the skill manager
    print("Checking skill installation status...")
    success, message = ensure_skill_installed()
    print(f"Result: {message}")
    
    if success:
        path = get_skill_path()
        if path:
            print(f"Skill path: {path}")
