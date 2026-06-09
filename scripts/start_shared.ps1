[CmdletBinding()]
param(
    [int]$Port = 8501,
    [string]$PublicHost = "",
    [string]$Python = "D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-PreferredSharedHost {
    try {
        $addresses = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
            Where-Object {
                $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
                -not [System.Net.IPAddress]::IsLoopback($_) -and
                -not $_.ToString().StartsWith("169.254.")
            }
        if ($addresses -and $addresses.Count -gt 0) {
            return $addresses[0].ToString()
        }
    }
    catch {
        return ""
    }
    return ""
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

$DisplayHost = $PublicHost.Trim()
if (-not $DisplayHost) {
    $DisplayHost = Get-PreferredSharedHost
}
if (-not $DisplayHost) {
    $DisplayHost = "<this-machine-ip>"
}

$StreamlitArgs = @(
    "-m", "streamlit", "run", "app.py",
    "--server.address", "0.0.0.0",
    "--server.port", "$Port",
    "--server.headless", "true",
    "--browser.serverAddress", "$DisplayHost",
    "--browser.serverPort", "$Port",
    "--browser.gatherUsageStats", "false"
)

Write-Host "Water erosion platform shared start"
Write-Host "Project root: $Root"
Write-Host "Local URL:   http://127.0.0.1:$Port/"
Write-Host "Shared URL:  http://${DisplayHost}:$Port/"
Write-Host "Bind:        0.0.0.0:$Port"
Write-Host "Security:    Use only on a trusted LAN or behind VPN/HTTPS/auth reverse proxy."

if ($DryRun) {
    Write-Host "Dry run command:"
    Write-Host "$Python $($StreamlitArgs -join ' ')"
    exit 0
}

Push-Location $Root
try {
    & $Python @StreamlitArgs
}
finally {
    Pop-Location
}
