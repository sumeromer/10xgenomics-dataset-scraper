#!/usr/bin/env python3
"""
Test script for MCP servers

This script tests that all MCP servers are properly configured and can be imported.
It does NOT test actual tool execution (which requires an MCP client like Claude Code).

Usage:
    micromamba activate 10XGenomics_scraper
    python test_mcp_servers.py
"""

import sys
from pathlib import Path

# Add mcp-servers to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers"))

def test_imports():
    """Test that all server modules can be imported."""
    print("Testing MCP server imports...")

    errors = []

    # Test scraper server
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "10x-scraper"))
        import server as scraper_server
        print("✅ Scraper server imports successfully")

        # Check for expected tools
        expected_tools = ['scrape_datasets', 'get_scraper_output', 'check_scraper_status']
        for tool in expected_tools:
            if hasattr(scraper_server, tool):
                print(f"   ✅ Tool found: {tool}")
            else:
                errors.append(f"Scraper tool not found: {tool}")
                print(f"   ❌ Tool not found: {tool}")

    except ImportError as e:
        errors.append(f"Failed to import scraper server: {e}")
        print(f"❌ Failed to import scraper server: {e}")

    # Test validator server
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "10x-validator"))
        import server as validator_server
        print("✅ Validator server imports successfully")

        expected_tools = ['validate_datasets', 'get_validation_report', 'check_validation_status']
        for tool in expected_tools:
            if hasattr(validator_server, tool):
                print(f"   ✅ Tool found: {tool}")
            else:
                errors.append(f"Validator tool not found: {tool}")
                print(f"   ❌ Tool not found: {tool}")

    except ImportError as e:
        errors.append(f"Failed to import validator server: {e}")
        print(f"❌ Failed to import validator server: {e}")

    # Test enricher server
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "mcp-servers" / "10x-enricher"))
        import server as enricher_server
        print("✅ Enricher server imports successfully")

        expected_tools = ['enrich_metadata', 'get_enriched_data', 'check_enrichment_status', 'get_field_statistics']
        for tool in expected_tools:
            if hasattr(enricher_server, tool):
                print(f"   ✅ Tool found: {tool}")
            else:
                errors.append(f"Enricher tool not found: {tool}")
                print(f"   ❌ Tool not found: {tool}")

    except ImportError as e:
        errors.append(f"Failed to import enricher server: {e}")
        print(f"❌ Failed to import enricher server: {e}")

    return errors


def test_fastmcp_available():
    """Test that FastMCP is installed."""
    print("\nTesting FastMCP availability...")

    try:
        from mcp.server.fastmcp import FastMCP
        print("✅ FastMCP is installed")
        return []
    except ImportError as e:
        error = f"FastMCP not installed: {e}"
        print(f"❌ {error}")
        print("\nTo install FastMCP, run:")
        print("    pip install fastmcp")
        return [error]


def test_skill_scripts_exist():
    """Test that skill scripts exist."""
    print("\nTesting skill scripts existence...")

    errors = []

    scripts = [
        ("Scraper", PROJECT_ROOT / "skills" / "scraper" / "scraper.py"),
        ("Validator", PROJECT_ROOT / "skills" / "validator" / "validator.py"),
        ("Enricher", PROJECT_ROOT / "skills" / "metadata_enricher" / "metadata_enricher.py")
    ]

    for name, path in scripts:
        if path.exists():
            print(f"✅ {name} script exists: {path}")
        else:
            error = f"{name} script not found: {path}"
            errors.append(error)
            print(f"❌ {error}")

    return errors


def test_config_file():
    """Test that MCP config file exists and is valid JSON."""
    print("\nTesting MCP configuration file...")

    config_file = PROJECT_ROOT / "mcp-servers" / "mcp-config.json"

    if not config_file.exists():
        error = f"MCP config file not found: {config_file}"
        print(f"❌ {error}")
        return [error]

    try:
        import json
        config = json.loads(config_file.read_text())
        print(f"✅ MCP config file exists and is valid JSON")

        # Check for expected servers
        if "mcpServers" in config:
            servers = config["mcpServers"]
            expected_servers = ["10x-genomics-scraper", "10x-genomics-validator", "10x-genomics-enricher"]

            for server_name in expected_servers:
                if server_name in servers:
                    print(f"   ✅ Server configured: {server_name}")
                else:
                    print(f"   ⚠️  Server not configured: {server_name}")
        else:
            print("   ⚠️  'mcpServers' key not found in config")

        return []
    except Exception as e:
        error = f"Failed to parse MCP config: {e}"
        print(f"❌ {error}")
        return [error]


def main():
    """Run all tests."""
    print("="*60)
    print("10X Genomics MCP Servers - Test Suite")
    print("="*60)
    print()

    all_errors = []

    # Run tests
    all_errors.extend(test_fastmcp_available())
    all_errors.extend(test_skill_scripts_exist())
    all_errors.extend(test_config_file())
    all_errors.extend(test_imports())

    # Summary
    print("\n" + "="*60)
    if all_errors:
        print(f"❌ Tests completed with {len(all_errors)} error(s):")
        for error in all_errors:
            print(f"   - {error}")
        print("\nPlease fix the errors above before using the MCP servers.")
        sys.exit(1)
    else:
        print("✅ All tests passed!")
        print("\nMCP servers are ready to use.")
        print("\nNext steps:")
        print("1. Add servers to ~/.config/claude-code/mcp_settings.json")
        print("2. Restart Claude Code")
        print("3. Start using the tools via natural language")
        print("\nSee mcp-servers/README.md for detailed setup instructions.")
        sys.exit(0)


if __name__ == "__main__":
    main()
