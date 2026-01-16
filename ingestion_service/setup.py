#!/usr/bin/env python3
"""
Setup script for FastAPI Ingestion Service.
Generates encryption keys and helps configure the service.
"""
import sys
import os
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("Installing required packages...")
    os.system("pip install cryptography")
    from cryptography.fernet import Fernet


def generate_encryption_key():
    """Generate a Fernet encryption key."""
    return Fernet.generate_key().decode()


def generate_api_key():
    """Generate a random API key."""
    import secrets
    return secrets.token_urlsafe(32)


def create_env_file():
    """Create .env file with generated keys."""
    env_path = Path(__file__).parent / ".env"
    example_path = Path(__file__).parent / ".env.example"

    # Check if .env already exists
    if env_path.exists():
        print(f"\n[ERROR] .env file already exists at {env_path}")
        print("Please delete it first if you want to regenerate keys.")
        return False

    # Read example file
    if example_path.exists():
        with open(example_path, 'r') as f:
            env_content = f.read()
    else:
        env_content = """# FastAPI Ingestion Service Environment Variables

# Application
APP_NAME=SAP B1 Ingestion Service
APP_VERSION=1.0.0
DEBUG=false

# API Keys (comma-separated list of valid keys)
API_KEYS=

# Encryption (Fernet key for payload encryption)
ENCRYPTION_KEY=

# Database (Railway PostgreSQL)
DATABASE_URL=

# CORS (comma-separated origins)
CORS_ORIGINS=*

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
"""

    # Generate keys
    encryption_key = generate_encryption_key()
    api_key = generate_api_key()

    # Replace placeholders
    env_content = env_content.replace("API_KEYS=", f"API_KEYS={api_key}")
    env_content = env_content.replace("ENCRYPTION_KEY=", f"ENCRYPTION_KEY={encryption_key}")

    # Write .env file
    with open(env_path, 'w') as f:
        f.write(env_content)

    print(f"\n[SUCCESS] Created .env file at {env_path}")
    print("\n" + "="*60)
    print("IMPORTANT: Save these credentials securely!")
    print("="*60)
    print(f"\nEncryption Key (share with SAP Middleware):")
    print(f"  {encryption_key}")
    print(f"\nAPI Key (use in X-API-Key header):")
    print(f"  {api_key}")
    print("\n" + "="*60)
    print("\nNext steps:")
    print("1. Add DATABASE_URL to .env (Railway PostgreSQL connection string)")
    print("2. Start the service: uvicorn app.main:app --reload")
    print("3. Test with: python ../tests/test_ingestion_harness.py")

    return True


def print_railway_commands():
    """Print Railway setup commands."""
    print("\n" + "="*60)
    print("RAILWAY DEPLOYMENT COMMANDS")
    print("="*60)
    print("\n1. Link Railway project:")
    print("   railway link")
    print("\n2. Set environment variables:")
    print("   railway variables set ENCRYPTION_KEY=<your-key>")
    print("   railway variables set API_KEYS=<your-api-keys>")
    print("   railway variables set DATABASE_URL=$DATABASE_URL")
    print("\n3. Deploy:")
    print("   railway up")
    print("\n4. View logs:")
    print("   railway logs")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Setup FastAPI Ingestion Service")
    parser.add_argument("--gen-key", action="store_true", help="Generate encryption key only")
    parser.add_argument("--gen-api-key", action="store_true", help="Generate API key only")
    parser.add_argument("--init", action="store_true", help="Initialize .env file")

    args = parser.parse_args()

    if args.gen_key:
        print(f"Encryption Key: {generate_encryption_key()}")
    elif args.gen_api_key:
        print(f"API Key: {generate_api_key()}")
    elif args.init:
        if create_env_file():
            print_railway_commands()
    else:
        # Interactive mode
        print("FastAPI Ingestion Service Setup")
        print("="*60)
        print("\nThis will:")
        print("1. Generate encryption key")
        print("2. Generate API key")
        print("3. Create .env file")
        print("\nContinue? (y/n): ", end="")

        if input().lower() == 'y':
            if create_env_file():
                print_railway_commands()
        else:
            print("Cancelled.")
