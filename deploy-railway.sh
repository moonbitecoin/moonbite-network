#!/bin/bash

echo "🚀 MoonBite PWA - Railway Deployment Script"
echo "============================================"

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "📥 Installing Railway CLI..."
    npm install -g @railway/cli
fi

# Check if connected to GitHub
if [ ! -d ".git" ]; then
    echo "❌ Not a git repository!"
    echo "Initialize with: git init"
    exit 1
fi

# Stage all changes
echo "📝 Staging changes..."
git add -A

# Ask for commit message
read -p "📝 Commit message: " commit_msg
if [ -z "$commit_msg" ]; then
    commit_msg="Update: MoonBite PWA deployment"
fi

# Commit
git commit -m "$commit_msg" || echo "⚠️  No changes to commit"

# Push to GitHub
echo "🔄 Pushing to GitHub..."
git push origin main

echo ""
echo "🎯 Railway Deployment Steps:"
echo "1. Go to https://railway.app"
echo "2. Click 'New Project' → 'Deploy from GitHub'"
echo "3. Select moonbitecoin/MoonBite-Coin"
echo "4. Wait for auto-deployment (2-3 minutes)"
echo "5. Set environment variables in Dashboard"
echo ""
echo "📱 After deployment, visit https://moonbite.org"
echo "   Then: Share > Add to Home Screen (iPhone/Android)"
echo ""
echo "✅ Deployment initiated!"
echo ""
echo "📖 See RAILWAY_DEPLOYMENT.md for detailed guide"
