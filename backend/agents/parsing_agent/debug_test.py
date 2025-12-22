#!/usr/bin/env python
"""
Simple debug script to test Django setup and imports.
Run this to see exactly where the import is failing.
"""
import sys
import os

# Get paths
current_file = os.path.abspath(__file__)
parsing_agent_dir = os.path.dirname(current_file)
agents_dir = os.path.dirname(parsing_agent_dir)
backend_dir = os.path.dirname(agents_dir)

print("=" * 60)
print("Path Information:")
print("=" * 60)
print(f"Current file: {current_file}")
print(f"Parsing agent dir: {parsing_agent_dir}")
print(f"Agents dir: {agents_dir}")
print(f"Backend dir: {backend_dir}")
print()

# Add backend to path
sys.path.insert(0, backend_dir)

print("=" * 60)
print("Python Path (first 5 entries):")
print("=" * 60)
for i, path in enumerate(sys.path[:5]):
    print(f"{i}: {path}")
print()

# Change to backend directory
os.chdir(backend_dir)
print(f"Working directory: {os.getcwd()}")
print()

# Check if core module exists
core_path = os.path.join(backend_dir, 'core')
print(f"Core directory exists: {os.path.exists(core_path)}")
print(f"Core __init__.py exists: {os.path.exists(os.path.join(core_path, '__init__.py'))}")
print()

# Try to set up Django
print("=" * 60)
print("Setting up Django...")
print("=" * 60)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    import django
    print(f"Django version: {django.get_version()}")
    django.setup()
    print("✓ Django setup successful!")
    print()
except Exception as e:
    print(f"✗ Django setup failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Try to import core.models
print("=" * 60)
print("Importing core.models...")
print("=" * 60)

try:
    from core.models import Prospectus
    print("✓ Successfully imported Prospectus from core.models")
    print(f"  Prospectus model: {Prospectus}")
    print()
except Exception as e:
    print(f"✗ Failed to import: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Try to import test
print("=" * 60)
print("Importing test module...")
print("=" * 60)

try:
    from agents.parsing_agent.test import ParseIndexPagesTestCase
    print("✓ Successfully imported ParseIndexPagesTestCase")
    print()
except Exception as e:
    print(f"✗ Failed to import test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 60)
print("All imports successful! You can now run tests.")
print("=" * 60)