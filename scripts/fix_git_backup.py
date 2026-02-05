#!/usr/bin/env python3
"""
Git Backup Repair Tool
Attempts to fix common git backup issues
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

def fix_ssh_known_hosts():
    """Add GitHub to SSH known_hosts"""
    print("🔧 Adding GitHub to SSH known_hosts...")
    success, stdout, stderr = run_cmd("ssh-keyscan -H github.com >> ~/.ssh/known_hosts")
    if success:
        print("✅ GitHub added to known_hosts")
        return True
    else:
        print(f"❌ Failed to add known_hosts: {stderr}")
        return False

def switch_to_https():
    """Switch remote from SSH to HTTPS for easier authentication"""
    print("🔧 Switching remote from SSH to HTTPS...")
    success, stdout, stderr = run_cmd("git remote set-url origin https://github.com/ryang4/BeStupid.git")
    if success:
        print("✅ Remote switched to HTTPS")
        return True
    else:
        print(f"❌ Failed to switch remote: {stderr}")
        return False

def test_connectivity():
    """Test if we can now connect to remote"""
    print("🔧 Testing remote connectivity...")
    success, stdout, stderr = run_cmd("git ls-remote origin HEAD")
    if success:
        print("✅ Remote connectivity working")
        return True
    else:
        print(f"❌ Still can't connect: {stderr}")
        return False

def commit_changes():
    """Commit the current changes"""
    print("🔧 Committing current changes...")
    
    # Add files
    success, stdout, stderr = run_cmd("git add .")
    if not success:
        print(f"❌ Failed to add files: {stderr}")
        return False
    
    # Commit
    commit_msg = "Auto-backup: Fix git authentication issues"
    success, stdout, stderr = run_cmd(f'git commit -m "{commit_msg}"')
    if success:
        print("✅ Changes committed")
        return True
    else:
        print(f"❌ Failed to commit: {stderr}")
        return False

def sync_with_remote():
    """Attempt to sync with remote"""
    print("🔧 Syncing with remote...")
    
    # Try to pull first (in case we're behind)
    success, stdout, stderr = run_cmd("git pull origin main --rebase")
    if success:
        print("✅ Pulled latest changes")
    else:
        print(f"⚠️  Pull failed (continuing): {stderr}")
    
    # Try to push
    success, stdout, stderr = run_cmd("git push origin main")
    if success:
        print("✅ Successfully pushed to remote")
        return True
    else:
        print(f"❌ Push failed: {stderr}")
        return False

def main():
    print("=== GIT BACKUP REPAIR ===")
    
    # Step 1: Try fixing SSH first
    if fix_ssh_known_hosts():
        if test_connectivity():
            print("✅ SSH authentication fixed!")
        else:
            print("⚠️  SSH still not working, trying HTTPS...")
            switch_to_https()
            if not test_connectivity():
                print("❌ Both SSH and HTTPS failed. Manual intervention needed.")
                return False
    else:
        # If SSH keyscan fails, try HTTPS
        switch_to_https()
        if not test_connectivity():
            print("❌ Cannot establish remote connectivity. Check credentials.")
            return False
    
    # Step 2: Commit current changes
    if not commit_changes():
        print("⚠️  Could not commit changes, but connectivity is fixed")
        return False
    
    # Step 3: Sync with remote
    if sync_with_remote():
        print("🎉 Git backup fully restored!")
        return True
    else:
        print("⚠️  Connectivity fixed but sync issues remain")
        return False

if __name__ == "__main__":
    main()