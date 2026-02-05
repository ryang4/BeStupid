#!/usr/bin/env python3
"""
Git Backup Diagnostic Tool
Analyzes and attempts to fix common git backup issues
"""
import subprocess
import os
import sys
from pathlib import Path

def run_cmd(cmd, timeout=30):
    """Run a command and return (success, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, 
            timeout=timeout, cwd="/project"
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def main():
    print("=== GIT BACKUP DIAGNOSTIC ===")
    
    # 1. Check git status
    print("\n1. Git Status:")
    success, stdout, stderr = run_cmd("git status --porcelain")
    if success:
        if stdout:
            print(f"Uncommitted changes:\n{stdout}")
        else:
            print("Working directory clean")
    else:
        print(f"ERROR: {stderr}")
    
    # 2. Check current branch
    print("\n2. Current Branch:")
    success, stdout, stderr = run_cmd("git branch --show-current")
    if success:
        print(f"Current branch: {stdout}")
    else:
        print(f"ERROR: {stderr}")
    
    # 3. Check remote configuration
    print("\n3. Remote Configuration:")
    success, stdout, stderr = run_cmd("git remote -v")
    if success:
        print(stdout)
    else:
        print(f"ERROR: {stderr}")
    
    # 4. Check last few commits
    print("\n4. Recent Commits:")
    success, stdout, stderr = run_cmd("git log --oneline -5")
    if success:
        print(stdout)
    else:
        print(f"ERROR: {stderr}")
    
    # 5. Check if we're behind remote
    print("\n5. Remote Sync Status:")
    success, stdout, stderr = run_cmd("git fetch origin --dry-run")
    if success:
        print("Fetch completed successfully")
        # Check if behind
        success, stdout, stderr = run_cmd("git status -uno")
        if "behind" in stdout:
            print("⚠️  Local branch is behind remote")
        elif "ahead" in stdout:
            print("⚠️  Local branch is ahead of remote")
        else:
            print("✅ Local and remote are in sync")
    else:
        print(f"Fetch failed: {stderr}")
    
    # 6. Check authentication method
    print("\n6. Authentication Check:")
    success, stdout, stderr = run_cmd("git ls-remote origin HEAD")
    if success:
        print("✅ Authentication working")
    else:
        if "could not read Username" in stderr:
            print("❌ HTTPS authentication failing - needs credentials")
        elif "Host key verification failed" in stderr:
            print("❌ SSH key authentication failing")
        else:
            print(f"❌ Authentication error: {stderr}")
    
    # 7. Suggest fixes
    print("\n=== RECOMMENDED FIXES ===")
    
    # Check for branch name issues
    success, current_branch, _ = run_cmd("git branch --show-current")
    success2, remotes, _ = run_cmd("git remote -v")
    
    if "master" in remotes and current_branch == "main":
        print("🔧 Branch mismatch detected (local=main, remote=master)")
    elif "main" in remotes and current_branch == "master":
        print("🔧 Branch mismatch detected (local=master, remote=main)")
    
    # Check for authentication issues
    success, _, stderr = run_cmd("git ls-remote origin HEAD")
    if not success:
        if "could not read Username" in stderr:
            print("🔧 Fix HTTPS auth: Set up git credentials or switch to SSH")
        elif "Host key verification failed" in stderr:
            print("🔧 Fix SSH auth: Add GitHub to known_hosts or regenerate SSH keys")

if __name__ == "__main__":
    main()