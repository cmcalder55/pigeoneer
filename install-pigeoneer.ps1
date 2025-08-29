# Install script for Pigeoneer - PoE Trade Message Watcher
$ErrorActionPreference = "Stop"

try {
    $ScriptPath = Join-Path $PSScriptRoot "run.py"
    if (-not (Test-Path $ScriptPath)) {
        throw "run.py not found in script directory"
    }

    # Ensure Python is available
    $Pythonw = $null
    try {
        $Pythonw = (Get-Command pythonw.exe).Source
    } catch {
        throw "pythonw.exe not found. Please install Python and ensure it's in your PATH"
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}

$TaskName = "PigeoneerTradeWatcher"

# Default game installation paths
$SteamPath = "C:/Program Files (x86)/Steam/steamapps/common"
$StandalonePath = "C:/Program Files (x86)/Grinding Gear Games"

# Create .env template if it doesn't exist
$EnvTemplate = @"
# Telegram Bot Configuration
TG_TOKEN=your_telegram_bot_token_here
TG_CHAT=your_chat_id_or_@username_here

# Path to PoE Client Log files
# Steam installation:
CLIENT_LOG_POE1=$SteamPath/Path of Exile/logs/Client.txt
CLIENT_LOG_POE2=$SteamPath/Path of Exile 2/logs/Client.txt

# For standalone client, use:
# CLIENT_LOG_POE1=$StandalonePath/Path of Exile/logs/Client.txt
# CLIENT_LOG_POE2=$StandalonePath/Path of Exile 2/logs/Client.txt
"@

$EnvTemplatePath = Join-Path $PSScriptRoot ".env.template"
if (-not (Test-Path $EnvTemplatePath)) {
    $EnvTemplate | Out-File -FilePath $EnvTemplatePath -Encoding UTF8
}

# Scheduled task: run pythonw.exe with the script at user logon, hidden
$Action   = New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$ScriptPath`""
$Trigger  = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
             -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType InteractiveToken

# Create / update task
$TaskDescription = "Pigeoneer - Path of Exile Trade Message Watcher for Telegram notifications"
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
        -Settings $Settings -Principal $Principal -Description $TaskDescription -Force
} catch {
    Write-Warning "Failed to register task: $($_.Exception.Message)"
    Write-Host "Attempting to unregister and recreate..."
    
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
        -Settings $Settings -Principal $Principal -Description $TaskDescription
}

# Check if .env exists, if not, create from template with a warning
$EnvPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $EnvPath)) {
    Copy-Item -Path $EnvTemplatePath -Destination $EnvPath
    Write-Warning "Created new .env file. Please edit it with your Telegram bot token and chat ID before running!"
    Write-Host "Edit the .env file at: $EnvPath"
    exit 1
}

# Start the task
try {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "`nSuccessfully installed and started '$TaskName'"
    Write-Host "Configuration file: $EnvPath"
    Write-Host "Log file: $ScriptPath\pigeoneer.log"
    
    Write-Host "`nTo uninstall, run:"
    Write-Host "Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
} catch {
    Write-Error "Failed to start task: $($_.Exception.Message)"
    Write-Warning "The task is installed but couldn't be started. You can start it manually from Task Scheduler."
}
