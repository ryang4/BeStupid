#!/usr/bin/env python3
"""
Robust Git Backup for Docker Containers
Handles sync conflicts, timeouts, and authentication issues gracefully
"""
import subprocess
import os
import sys
import time
from pathlib import Path
from datetime import datetime

def run_cmd(cmd, timeout=60, max_retries=3):
    """Run a command with retries and timeout handling"""
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd="/project"
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            print(f"Command timed out (attempt {attempt + 1}/{max_retries}): {cmd}")
            if attempt < max_retries - 1:
                time.sleep(5)  # Wait before retry
            continue
        except Exception as e:
            print(f"Command failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
    
    return False, "", "Max retries exceeded"

def force_sync_with_remote():
    """Aggressively sync with remote, handling conflicts"""
    print("🔧 Force syncing with remote...")
    
    # Step 1: Fetch everything
    success, stdout, stderr = run_cmd("git fetch origin", timeout=30)
    if not success:
        print(f"❌ Fetch failed: {stderr}")
        return False
    
    # Step 2: Check if we're behind
    success, stdout, stderr = run_cmd("git status -uno")
    
    if "behind" in stdout or "diverged" in stdout:
        print("⚠️  Local behind/diverged from remote - force syncing")
        
        # Step 3: Create backup of local changes
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        success, stdout, stderr = run_cmd(f"git stash push -m 'backup_before_sync_{timestamp}'")
        
        # Step 4: Hard reset to remote
        success, stdout, stderr = run_cmd("git reset --hard origin/main", timeout=30)
        if not success:
            print(f"❌ Hard reset failed: {stderr}")
            return False
        
        # Step 5: Restore stashed changes if any
        success, stdout, stderr = run_cmd("git stash list")
        if f"backup_before_sync_{timestamp}" in stdout:
            print("🔄 Restoring local changes...")
            run_cmd("git stash pop")  # Don't fail if this doesn't work
    
    print("✅ Force sync completed")
    return True

def safe_commit_and_push():
    """Safely commit and push changes"""
    print("🔧 Safe commit and push...")
    
    # Step 1: Check if there are changes
    success, stdout, stderr = run_cmd("git status --porcelain")
    if not success or not stdout.strip():
        print("ℹ️  No changes to commit")
        return True
    
    # Step 2: Add all changes
    success, stdout, stderr = run_cmd("git add .", timeout=30)
    if not success:
        print(f"❌ Add failed: {stderr}")
        return False
    
    # Step 3: Commit with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-backup: {timestamp}"
    
    success, stdout, stderr = run_cmd(f'git commit -m "{commit_msg}"', timeout=30)
    if not success:
        if "nothing to commit" in stderr:
            print("ℹ️  Nothing to commit")
            return True
        print(f"❌ Commit failed: {stderr}")
        return False
    
    # Step 4: Push with retry logic
    for attempt in range(3):
        success, stdout, stderr = run_cmd("git push origin main", timeout=60)
        if success:
            print("✅ Push successful")
            return True
        
        if "non-fast-forward" in stderr or "rejected" in stderr:
            print(f"⚠️  Push rejected (attempt {attempt + 1}) - syncing and retrying...")
            if not force_sync_with_remote():
                continue
            
            # Try to recommit after sync
            success, stdout, stderr = run_cmd(f'git commit -m "{commit_msg}"', timeout=30)
            # Continue to next push attempt
        else:
            print(f"❌ Push failed (attempt {attempt + 1}): {stderr}")
            time.sleep(5)
    
    print("❌ Push failed after all retries")
    return False

def health_check():
    """Quick health check of git setup"""
    print("🔍 Git health check...")
    
    # Check if we're in a git repo
    success, stdout, stderr = run_cmd("git rev-parse --git-dir")
    if not success:
        print("❌ Not in a git repository")
        return False
    
    # Check remote connectivity
    success, stdout, stderr = run_cmd("git ls-remote origin HEAD", timeout=30)
    if not success:
        print(f"❌ Cannot connect to remote: {stderr}")
        return False
    
    print("✅ Git health check passed")
    return True

def main():
    print("=== ROBUST GIT BACKUP ===")
    print(f"Starting at {datetime.now()}")
    
    # Step 1: Health check
    if not health_check():
        print("💔 Health check failed - aborting")
        return False
    
    # Step 2: Force sync to get clean state
    if not force_sync_with_remote():
        print("💔 Force sync failed - aborting")
        return False
    
    # Step 3: Safe commit and push
    if not safe_commit_and_push():
        print("💔 Commit/push failed")
        return False
    
    print("🎉 Robust backup completed successfully!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)