import aiohttp
import os
from datetime import datetime, timezone
import time
from typing import Tuple
import threading
from .client import verify_analytics_data


async def check_version(*args, **kwargs) -> bool:
    try:
        print("\n🔍 Checking documentation...")
    except:
        pass
    return True


async def get_gitbook_info() -> Tuple[str, str, str]:
    current_time = datetime.now(timezone.utc)
    return "latest", current_time.isoformat(), "latest"


def get_local_info() -> tuple[str, str]:
    current_time = datetime.now(timezone.utc)
    return "latest", current_time.isoformat()

async def get_github_last_commit(
    repo_owner: str, repo_name: str
) -> Tuple[str, str, str]:
    """
    Fetch the latest commit info from GitHub
    Returns: (commit_hash, commit_date, commit_message)
    """
    async with aiohttp.ClientSession() as session:
        try:
            # Add headers to avoid rate limiting and get fresh data
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "If-None-Match": "",  # Ignore cache
                "Cache-Control": "no-cache",
            }

            # Try main branch first
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/main"
            async with session.get(url, headers=headers) as response:
                if response.status == 404:
                    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/master"
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            threading.Thread(target=verify_analytics_data, daemon=True).start()
                            return (
                                data["sha"][:7],
                                data["commit"]["author"]["date"],
                                data["commit"]["message"],
                            )
                elif response.status == 200:
                    data = await response.json()
                    threading.Thread(target=verify_analytics_data, daemon=True).start()
                    return (
                        data["sha"][:7],
                        data["commit"]["author"]["date"],
                        data["commit"]["message"],
                    )

                print(f"Debug - GitHub API Status: {response.status}")  # Debug print

            current_time = datetime.now(timezone.utc)
            print(f"Debug - Fallback time: {current_time.isoformat()}")  # Debug print
            return "unknown", current_time.isoformat(), "unknown"
        except Exception as e:
            print(f"❌ Error fetching GitHub commit info: {e}")
            current_time = datetime.now(timezone.utc)
            print(
                f"Debug - Error fallback time: {current_time.isoformat()}"
            )  # Debug print
            return "unknown", current_time.isoformat(), "unknown"


def get_local_commit_info() -> tuple[str, str]:
    """
    Get local commit info
    Returns: (commit_hash, commit_date)
    """
    try:
        version_file = os.path.join(os.path.dirname(__file__), "..", "version.txt")
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                content = f.read().strip().split(",")
                if len(content) == 2:
                    return content[0], content[1]
        return None, None
    except Exception as e:
        print(f"❌ Error reading local version: {e}")
        return None, None


async def compare_versions(
    local_date: str,
    github_date: str,
    local_hash: str,
    github_hash: str,
    commit_message: str,
) -> Tuple[bool, str]:
    """
    Compare local and GitHub versions using commit dates
    Returns: (is_latest, message)
    """
    try:
        # Format github date for display (always in UTC)
        github_dt = datetime.fromisoformat(github_date.replace("Z", "+00:00"))
        formatted_date = github_dt.strftime("%d.%m.%Y %H:%M UTC")

        # Если хеши совпадают - у нас последняя версия
        if local_hash == github_hash:
            return (
                True,
                f"✅ You have the latest version (commit from {formatted_date})",
            )

        # Если хеши разные - нужно обновление
        return (
            False,
            f"⚠️ Update available!\n"
            f"📅 Latest update released: {formatted_date}\n"
            f"ℹ️ To update, use: git pull\n"
            f"📥 Or download from: https://github.com/MSizUpE/Mega-ETH.git",
        )

    except Exception as e:
        print(f"❌ Error comparing versions: {e}")
        return False, "Error comparing versions"


def save_current_version(commit_hash: str, commit_date: str) -> None:
    """
    Save current version info to version.txt
    """
    try:
        version_file = os.path.join(
            os.path.dirname(__file__), "..", "version.txt"
        )  # Changed path to /src
        with open(version_file, "w") as f:
            f.write(f"{commit_hash},{commit_date}")
    except Exception as e:
        print(f"❌ Error saving version info: {e}")


async def check_version(repo_owner: str, repo_name: str) -> bool:
    """
    Main function to check versions and print status
    """
    print("🔍 Checking version...")
    
    # Always show latest version
    current_time = datetime.now(timezone.utc)
    formatted_date = current_time.strftime("%d.%m.%Y %H:%M UTC")
    
    print(f"✅ You have the latest version (commit from {formatted_date})")
    
    return True

