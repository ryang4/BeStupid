# Git Sync Wrapper for Scheduled Tasks
# Usage: .\run_with_git_sync.ps1 -Task <daily|metrics>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("daily", "metrics")]
    [string]$Task
)

# Configuration
$RepoRoot = "C:\Users\galli\OneDrive\BeStupid"
$ScriptsDir = "$RepoRoot\scripts"
$LogFile = "$ScriptsDir\logs\sync_errors.log"
# WSL path equivalent (OneDrive path in WSL)
$WslRepoRoot = "/mnt/c/Users/galli/OneDrive/BeStupid"

# Ensure log directory exists
if (-not (Test-Path "$ScriptsDir\logs")) {
    New-Item -ItemType Directory -Path "$ScriptsDir\logs" -Force | Out-Null
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $LogFile -Value $logEntry
    Write-Host $logEntry
}

function Invoke-GitSync {
    param(
        [string[]]$Scripts,
        [string]$CommitMessage
    )

    try {
        Set-Location $RepoRoot

        # Step 1: Git Pull
        Write-Log "Pulling latest changes..."
        $pullResult = git pull 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Git pull failed: $pullResult" "ERROR"
            return $false
        }
        Write-Log "Pull complete: $pullResult"

        # Step 2: Run Python script(s) via WSL (use login shell for PATH)
        foreach ($script in $Scripts) {
            Write-Log "Running $script via WSL..."
            # Run from repo root so relative paths work, but reference script in scripts/
            $wslCommand = "cd '$WslRepoRoot' && uv run --project scripts python scripts/$script"
            $scriptResult = wsl bash -lc $wslCommand 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Log "Script $script failed: $scriptResult" "ERROR"
                return $false
            }
            Write-Log "Script $script completed successfully"
        }

        # Step 3: Git Add
        Set-Location $RepoRoot
        Write-Log "Staging changes..."
        $addResult = git add -A 2>&1
        Write-Log "Staged: $addResult"

        # Step 4: Check if there are changes to commit
        $status = git status --porcelain
        if ([string]::IsNullOrWhiteSpace($status)) {
            Write-Log "No changes to commit"
            return $true
        }

        # Step 5: Git Commit
        Write-Log "Committing changes..."
        $commitResult = git commit -m $CommitMessage 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Git commit failed: $commitResult" "ERROR"
            return $false
        }
        Write-Log "Commit complete"

        # Step 6: Git Push
        Write-Log "Pushing to remote..."
        $pushResult = git push 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Git push failed: $pushResult" "ERROR"
            return $false
        }
        Write-Log "Push complete"

        return $true
    }
    catch {
        Write-Log "Unexpected error: $_" "ERROR"
        return $false
    }
}

# Main execution
Write-Log "========== Starting $Task task =========="

switch ($Task) {
    "daily" {
        $scripts = @("daily_planner.py")
        $message = "🤖 Auto-sync: Daily planner"
    }
    "metrics" {
        $scripts = @("metrics_extractor.py", "dashboard.py")
        $message = "🤖 Auto-sync: Metrics and dashboard"
    }
}

$success = Invoke-GitSync -Scripts $scripts -CommitMessage $message

if ($success) {
    Write-Log "========== $Task task completed successfully =========="
    exit 0
} else {
    Write-Log "========== $Task task failed =========="
    exit 1
}
