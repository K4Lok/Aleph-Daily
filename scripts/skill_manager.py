"""
Skill Manager for news-aggregator-skill.
Handles checking installation status and installing the skill if needed.
"""

import os
import subprocess
import shutil
from pathlib import Path


SKILL_NAME = "news-aggregator-skill"
SKILL_REPO_URL = "https://github.com/cclank/news-aggregator-skill"

# Possible installation locations
SKILL_PATHS = [
    Path.home() / ".claude" / "skills" / SKILL_NAME,
    Path.home() / ".claude" / "skills" / SKILL_NAME / "SKILL.md",
]


def is_skill_installed() -> bool:
    """
    Check if news-aggregator-skill is installed.
    
    Returns:
        True if the skill is found in any known location.
    """
    # Check ~/.claude/skills/news-aggregator-skill/SKILL.md
    skill_md_path = Path.home() / ".claude" / "skills" / SKILL_NAME / "SKILL.md"
    if skill_md_path.exists():
        return True
    
    # Check if the skill directory exists with any content
    skill_dir = Path.home() / ".claude" / "skills" / SKILL_NAME
    if skill_dir.exists() and any(skill_dir.iterdir()):
        return True
    
    return False


def install_skill() -> tuple[bool, str]:
    """
    Install news-aggregator-skill using npx skills add.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    print(f"[SkillManager] Installing {SKILL_NAME}...")
    
    # Check if npx is available
    if not shutil.which("npx"):
        return False, "npx is not installed. Please install Node.js and npm first."
    
    try:
        # Run npx skills add
        result = subprocess.run(
            ["npx", "skills", "add", SKILL_REPO_URL],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout for installation
        )
        
        if result.returncode == 0:
            print(f"[SkillManager] Successfully installed {SKILL_NAME}")
            return True, f"Successfully installed {SKILL_NAME}"
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            print(f"[SkillManager] Installation failed: {error_msg}")
            return False, f"Installation failed: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return False, "Installation timed out after 2 minutes"
    except FileNotFoundError:
        return False, "npx command not found. Please install Node.js and npm."
    except Exception as e:
        return False, f"Unexpected error during installation: {str(e)}"


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
    skill_dir = Path.home() / ".claude" / "skills" / SKILL_NAME
    if skill_dir.exists():
        return skill_dir
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
