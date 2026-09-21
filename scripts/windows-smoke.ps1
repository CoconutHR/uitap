[CmdletBinding()]
param(
    [switch]$Install,
    [string]$Config
)

# Windows 薄包装：真正的跨平台实现在 scripts/smoke.py，两个平台共用同一份逻辑。
$ErrorActionPreference = "Stop"

$arguments = @((Join-Path $PSScriptRoot "smoke.py"))
if ($Config) { $arguments += @("--config", $Config) }
if ($Install) { $arguments += "--install" }

$Python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
& $Python @arguments
exit $LASTEXITCODE
