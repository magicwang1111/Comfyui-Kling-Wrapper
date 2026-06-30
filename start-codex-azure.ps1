[CmdletBinding()]
param(
    [string]$Endpoint = "https://goumee-ai-wuya-resource.services.ai.azure.com/openai/v1",
    [string]$Deployment = "gpt-5.4",
    [string]$ProfileDir = (Join-Path $env:LOCALAPPDATA "Codex\azure-openai-profile"),
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CodexArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertTo-TomlString {
    param([Parameter(Mandatory = $true)][string]$Value)
    return '"' + ($Value -replace '\\', '\\' -replace '"', '\"') + '"'
}

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "The 'codex' command was not found in PATH."
}

$hadAzureKey = -not [string]::IsNullOrWhiteSpace($env:AZURE_OPENAI_API_KEY)
if (-not $hadAzureKey) {
    $secureKey = Read-Host "Azure OpenAI API key" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $env:AZURE_OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null

$configPath = Join-Path $ProfileDir "config.toml"
$endpointToml = ConvertTo-TomlString $Endpoint
$deploymentToml = ConvertTo-TomlString $Deployment

@"
model = $deploymentToml
model_provider = "azure_openai"

[model_providers.azure_openai]
name = "Azure OpenAI"
base_url = $endpointToml
wire_api = "responses"
env_http_headers = { "api-key" = "AZURE_OPENAI_API_KEY" }
"@ | Set-Content -LiteralPath $configPath -Encoding utf8

$previousCodexHome = $env:CODEX_HOME
$hadCodexHome = Test-Path Env:\CODEX_HOME

try {
    $env:CODEX_HOME = $ProfileDir
    & codex @CodexArgs
    exit $LASTEXITCODE
}
finally {
    if ($hadCodexHome) {
        $env:CODEX_HOME = $previousCodexHome
    }
    else {
        Remove-Item Env:\CODEX_HOME -ErrorAction SilentlyContinue
    }

    if (-not $hadAzureKey) {
        Remove-Item Env:\AZURE_OPENAI_API_KEY -ErrorAction SilentlyContinue
    }
}
