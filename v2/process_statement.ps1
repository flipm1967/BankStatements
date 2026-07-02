# Process bank statements: load, categorize, and display
# Usage: .\process_statements.ps1 [path_to_ofx_file]
# If no file specified, uses the latest .ofx file in ../DATA/

param(
    [string]$OfxFile
)

# If no OFX file provided, find the latest one in ../DATA/
if (-not $OfxFile) {
    $dataPath = Resolve-Path "../DATA" -ErrorAction SilentlyContinue
    if (-not $dataPath) {
        Write-Error "DATA directory not found at ../DATA and no OFX file specified"
        exit 1
    }
    
    $latestOfx = Get-ChildItem -Path $dataPath -Filter "*.ofx" -ErrorAction SilentlyContinue |
                 Sort-Object -Property LastWriteTime -Descending |
                 Select-Object -First 1
    
    if (-not $latestOfx) {
        Write-Error "No .ofx files found in $dataPath"
        exit 1
    }
    
    $OfxFile = $latestOfx.FullName
    Write-Host "Found latest OFX file: $(Split-Path $OfxFile -Leaf)"
}

# Verify the file exists
if (-not (Test-Path $OfxFile)) {
    Write-Error "OFX file not found: $OfxFile"
    exit 1
}

Write-Host "`n=== Processing Bank Statements ===" -ForegroundColor Green
Write-Host "OFX File: $(Split-Path $OfxFile -Leaf)`n"

# Step 1: Load OFX into database
Write-Host "Step 1: Loading OFX into database..." -ForegroundColor Cyan
py load_statement_ofx.py "$OfxFile"
if ($LASTEXITCODE -ne 0) {
    Write-Error "load_statement_ofx.py failed with exit code $LASTEXITCODE"
    exit 1
}

# Step 2: Categorize transactions
Write-Host "`nStep 2: Categorizing transactions..." -ForegroundColor Cyan
py categorise_md.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "categorise_md.py failed with exit code $LASTEXITCODE"
    exit 1
}

# Step 3: Generate HTML report
Write-Host "`nStep 3: Generating HTML report..." -ForegroundColor Cyan
py display.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "display.py failed with exit code $LASTEXITCODE"
    exit 1
}

# Step 4: Open in browser
Write-Host "`nOpening report in browser..." -ForegroundColor Cyan
$displayPath = Resolve-Path "display.html"
Start-Process $displayPath

Write-Host "`n=== Processing Complete ===" -ForegroundColor Green
