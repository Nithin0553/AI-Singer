# Run in the PowerShell session that will start AI Singer.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$VolumeLabel,

    [switch]$Preview
)

$ErrorActionPreference = 'Stop'

# Resolve by label so the setup works if Windows reassigns the drive letter.
$volumes = @(
    Get-Volume | Where-Object {
        $_.FileSystemLabel -eq $VolumeLabel -and
        $null -ne $_.DriveLetter -and
        [string]$_.DriveLetter -ne ''
    }
)

if ($volumes.Count -ne 1) {
    throw "Expected exactly one mounted volume with label '$VolumeLabel'; found $($volumes.Count). Connect the correct drive and try again."
}

$volume = $volumes[0]
$driveRoot = "$($volume.DriveLetter):\"
$storageRoot = Join-Path -Path $driveRoot -ChildPath 'AI_Singer'
$directories = @(
    'models',
    'models\voice_conversion',
    'models\singing_synthesis',
    'models\audio_analysis',
    'datasets',
    'datasets\raw',
    'datasets\processed',
    'datasets\annotations',
    'cache',
    'cache\huggingface',
    'cache\torch',
    'outputs',
    'outputs\previews',
    'outputs\renders',
    'training',
    'training\checkpoints',
    'training\logs'
)

Write-Host "Selected '$($volume.FileSystemLabel)' ($($volume.FileSystem)) at $driveRoot"
Write-Host "AI Singer storage: $storageRoot"

if ($Preview) {
    Write-Host 'Preview only; no folders or environment variables were changed.'
    foreach ($relative in $directories) {
        Write-Host "  $(Join-Path -Path $storageRoot -ChildPath $relative)"
    }
    return
}

# Create only project directories; never format, rename, or clear the volume.
$paths = @($storageRoot)
foreach ($relative in $directories) {
    $paths += Join-Path -Path $storageRoot -ChildPath $relative
}

foreach ($path in $paths) {
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        throw "Cannot create storage directory because a file already exists: $path"
    }
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}

# Limit cache overrides to the current PowerShell process, not other projects.
$env:AI_SINGER_STORAGE_ROOT = $storageRoot
$env:HF_HOME = Join-Path -Path $storageRoot -ChildPath 'cache\huggingface'
$env:TORCH_HOME = Join-Path -Path $storageRoot -ChildPath 'cache\torch'

Write-Host 'Storage directories created or verified.'
Write-Host 'AI_SINGER_STORAGE_ROOT, HF_HOME, and TORCH_HOME are set for this PowerShell session.'
Write-Host 'Re-run this script in each new terminal, or after reconnecting the drive.'

