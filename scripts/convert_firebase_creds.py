#!/usr/bin/env python3
"""
Helper script to convert Firebase credentials JSON file to a single-line string
for use as an environment variable in Render or other deployment platforms.

Usage:
    python scripts/convert_firebase_creds.py path/to/firebase-credentials.json
"""

import json
import sys
import os


def convert_credentials_to_env_string(credentials_path):
    """
    Convert Firebase credentials JSON file to a single-line string.
    
    Args:
        credentials_path (str): Path to Firebase credentials JSON file
        
    Returns:
        str: Single-line JSON string ready for environment variable
    """
    if not os.path.exists(credentials_path):
        print(f"Error: File not found: {credentials_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(credentials_path, 'r') as f:
            creds = json.load(f)
        
        # Convert to single-line JSON string
        json_string = json.dumps(creds, separators=(',', ':'))
        
        return json_string
    
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in credentials file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/convert_firebase_creds.py <path-to-firebase-credentials.json>")
        print("\nExample:")
        print("  python scripts/convert_firebase_creds.py firebase-credentials.json")
        sys.exit(1)
    
    credentials_path = sys.argv[1]
    json_string = convert_credentials_to_env_string(credentials_path)
    
    print("\n" + "="*80)
    print("Firebase Credentials as Environment Variable String")
    print("="*80)
    print("\nCopy the following and paste it as the value for FIREBASE_CREDENTIALS_JSON:")
    print("\n" + "-"*80)
    print(json_string)
    print("-"*80)
    print("\nNote: This is a single-line JSON string. Make sure to copy it entirely.")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

