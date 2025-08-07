#!/usr/bin/env python3
"""
CET-Mentor v2.0 - Setup and Test Script
This script helps verify that your installation is working correctly.
"""

import os
import sys
import json
import importlib.util

def check_python_version():
    """Check if Python version is 3.9+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print("❌ Python 3.9+ is required. Current version:", f"{version.major}.{version.minor}")
        return False
    print(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def check_required_packages():
    """Check if all required packages are installed"""
    required_packages = [
        'flask', 'flask_session', 'requests', 'bs4', 'pandas', 
        'openai', 'dotenv', 'gunicorn', 'tqdm'
    ]
    
    missing_packages = []
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
        else:
            print(f"✅ {package} is installed")
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    return True

def check_data_file():
    """Check if data file exists and is valid"""
    if not os.path.exists('mht_cet_data.json'):
        print("❌ mht_cet_data.json not found")
        return False
    
    try:
        with open('mht_cet_data.json', 'r') as f:
            data = json.load(f)
        print(f"✅ Data file loaded successfully: {len(data)} college records")
        return True
    except json.JSONDecodeError:
        print("❌ mht_cet_data.json is not valid JSON")
        return False

def check_env_file():
    """Check environment configuration"""
    if not os.path.exists('.env'):
        print("⚠️  .env file not found. Copy .env.example to .env and configure your API keys")
        return False
    
    with open('.env', 'r') as f:
        env_content = f.read()
    
    if 'OPENROUTER_API_KEY' not in env_content:
        print("⚠️  OPENROUTER_API_KEY not found in .env file")
        return False
    
    if 'sk-or-v1-' not in env_content:
        print("⚠️  OPENROUTER_API_KEY appears to be a placeholder. Please set your actual API key")
        return False
    
    print("✅ Environment configuration looks good")
    return True

def test_app_import():
    """Test if the main app can be imported"""
    try:
        sys.path.insert(0, '.')
        import app
        print("✅ Flask app imports successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import app: {e}")
        return False

def main():
    """Run all checks"""
    print("🚀 CET-Mentor v2.0 - Setup Verification")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("Required Packages", check_required_packages),
        ("Data File", check_data_file),
        ("Environment Config", check_env_file),
        ("App Import", test_app_import)
    ]
    
    all_passed = True
    for name, check_func in checks:
        print(f"\n🔍 Checking {name}...")
        if not check_func():
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All checks passed! Your CET-Mentor setup is ready.")
        print("\nTo start the application:")
        print("  python3 app.py")
        print("\nThen open: http://localhost:5000")
    else:
        print("❌ Some checks failed. Please fix the issues above before running the app.")
        print("\nQuick fixes:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Configure environment: cp .env.example .env (then edit .env)")
        print("  3. Get API key from: https://openrouter.ai")

if __name__ == "__main__":
    main()