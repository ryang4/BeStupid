#!/usr/bin/env python3
import subprocess
import os

os.chdir("/project")

print("=== Git Status Debug ===")

try:
    # Check git status
    result = subprocess.run(["git", "status", "--porcelain"], 
                          capture_output=True, text=True, timeout=10)
    print(f"Git status exit code: {result.returncode}")
    print(f"Git status output:\n{result.stdout}")
    if result.stderr:
        print(f"Git status stderr:\n{result.stderr}")
    
    # Check git remote
    result = subprocess.run(["git", "remote", "-v"], 
                          capture_output=True, text=True, timeout=10)
    print(f"\nGit remote:\n{result.stdout}")
    
    # Check last commit
    result = subprocess.run(["git", "log", "-1", "--oneline"], 
                          capture_output=True, text=True, timeout=10)
    print(f"\nLast commit:\n{result.stdout}")
    
    # Check git config
    result = subprocess.run(["git", "config", "--list"], 
                          capture_output=True, text=True, timeout=10)
    print(f"\nGit config (first 10 lines):")
    for line in result.stdout.split('\n')[:10]:
        print(line)

except Exception as e:
    print(f"Error: {e}")