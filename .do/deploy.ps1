# Digital Ocean Deployment Script for Windows PowerShell

Write-Host "🚀 Starting Digital Ocean deployment..." -ForegroundColor Green

# Check if doctl is installed
try {
    $doctlVersion = doctl version
    Write-Host "✅ doctl is installed: $doctlVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ doctl is not installed. Please install it first:" -ForegroundColor Red
    Write-Host "   Download from: https://github.com/digitalocean/doctl/releases" -ForegroundColor Yellow
    Write-Host "   Or use: winget install digitalocean.doctl" -ForegroundColor Yellow
    exit 1
}

# Check if user is logged in
try {
    $authList = doctl auth list 2>&1
    if ($authList -match "Error") {
        throw "Not authenticated"
    }
    Write-Host "✅ doctl authentication verified" -ForegroundColor Green
} catch {
    Write-Host "❌ Please login to Digital Ocean first:" -ForegroundColor Red
    Write-Host "   doctl auth init" -ForegroundColor Yellow
    exit 1
}

# Check if app.yaml exists
if (-not (Test-Path ".do\app.yaml")) {
    Write-Host "❌ .do\app.yaml not found. Please run deploy_digitalocean.py first." -ForegroundColor Red
    exit 1
}

# Create app from spec
Write-Host "📦 Creating Digital Ocean app..." -ForegroundColor Blue
try {
    $result = doctl apps create --spec .do\app.yaml
    Write-Host "✅ App created successfully!" -ForegroundColor Green
    Write-Host $result
} catch {
    Write-Host "❌ Failed to create app: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🎉 App deployment initiated!" -ForegroundColor Green
Write-Host "📋 Next steps:" -ForegroundColor Yellow
Write-Host "   1. Go to your Digital Ocean dashboard" -ForegroundColor White
Write-Host "   2. Navigate to Apps → Your App → Settings" -ForegroundColor White
Write-Host "   3. Set environment variables:" -ForegroundColor White
Write-Host "      - SECRET_KEY: [Use the key from .env.production.example]" -ForegroundColor White
Write-Host "   4. Update GitHub repository URL in app settings" -ForegroundColor White
Write-Host "   5. Monitor deployment progress in the dashboard" -ForegroundColor White
Write-Host ""
Write-Host "🔗 Useful commands:" -ForegroundColor Cyan
Write-Host "   doctl apps list                    # List your apps" -ForegroundColor Gray
Write-Host "   doctl apps get <app-id>            # Get app details" -ForegroundColor Gray
Write-Host "   doctl apps logs <app-id> --follow  # View app logs" -ForegroundColor Gray
