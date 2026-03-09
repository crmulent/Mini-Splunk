#!/usr/bin/env python3
"""
Mini-Splunk Quick Start Test Script

This script demonstrates the key features of the Mini-Splunk system.
Run this after starting the server to test all functionality.

Usage:
    python quickstart.py [--host localhost] [--port 5514]
"""

import sys
import time
import argparse


def print_header(text):
    """Print a formatted header."""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)


def print_step(number, description):
    """Print a test step."""
    print(f"\n[Step {number}] {description}")
    print("-" * 70)


def test_ingest(client):
    """Test ingesting a syslog file."""
    print_step(1, "INGESTING SYSLOG FILE")
    
    try:
        result = client.ingest_file("sample_logs.txt")
        if result:
            print("✓ File ingestion successful")
            return True
        else:
            print("✗ File ingestion failed")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def test_search_date(client):
    """Test searching by date."""
    print_step(2, "SEARCHING LOGS BY DATE")
    
    try:
        result = client.search_date("Feb 22 00:0")
        if result:
            print("✓ Date search successful")
            return True
        else:
            print("✗ Date search failed")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def test_search_host(client):
    """Test searching by hostname."""
    print_step(3, "SEARCHING LOGS BY HOSTNAME")
    
    try:
        result = client.search_host("SYSSVR1")
        if result:
            print("✓ Host search successful")
            return True
        else:
            print("✗ Host search failed")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def test_search_daemon(client):
    """Test searching by daemon."""
    print_step(4, "SEARCHING LOGS BY DAEMON")
    
    try:
        result = client.search_daemon("kernel")
        if result:
            print("✓ Daemon search successful")
            return True
        else:
            print("✗ Daemon search failed")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def test_search_severity(client):
    """Test searching by severity."""
    print_step(5, "SEARCHING LOGS BY SEVERITY")
    
    try:
        result = client.search_severity("INFO")
        if result:
            print("✓ Severity search successful")
            return True
        else:
            print("✗ Severity search failed")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def test_search_keyword(client):
    """Test searching by keyword."""
    print_step(6, "SEARCHING LOGS BY KEYWORD")
    
    try:
        result = client.search_keyword("memory")
        if result:
            print("✓ Keyword search successful")
            return True
        else:
            print("✗ Keyword search failed")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def test_count_keyword(client):
    """Test counting keyword occurrences."""
    print_step(7, "COUNTING KEYWORD OCCURRENCES")
    
    try:
        result = client.count_keyword("kernel")
        if result:
            print("✓ Keyword count successful")
            return True
        else:
            print("✗ Keyword count failed")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def test_get_stats(client):
    """Test getting statistics."""
    print_step(8, "RETRIEVING SERVER STATISTICS")
    
    try:
        result = client.get_stats()
        if result:
            print("✓ Statistics retrieved successfully")
            return True
        else:
            print("✗ Statistics retrieval failed")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def test_get_help(client):
    """Test getting help."""
    print_step(9, "RETRIEVING HELP INFORMATION")
    
    try:
        result = client.get_help()
        if result:
            print("✓ Help information retrieved successfully")
            return True
        else:
            print("✗ Help retrieval failed")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False


def main():
    """Run all tests."""
    parser = argparse.ArgumentParser(description="Mini-Splunk Quick Start Test")
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=5514, help='Server port')
    
    args = parser.parse_args()
    
    # Import client
    try:
        from client import SyslogForwarderClient
    except ImportError:
        print("✗ Failed to import SyslogForwarderClient", file=sys.stderr)
        sys.exit(1)
    
    print_header("MINI-SPLUNK QUICK START TEST")
    print(f"Connecting to server at {args.host}:{args.port}...")
    
    # Create and connect client
    client = SyslogForwarderClient(host=args.host, port=args.port)
    
    if not client.connect():
        print("✗ Failed to connect to server", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Run tests
        tests = [
            ("Ingest File", test_ingest),
            ("Search by Date", test_search_date),
            ("Search by Host", test_search_host),
            ("Search by Daemon", test_search_daemon),
            ("Search by Severity", test_search_severity),
            ("Search by Keyword", test_search_keyword),
            ("Count Keyword", test_count_keyword),
            ("Get Statistics", test_get_stats),
            ("Get Help", test_get_help),
        ]
        
        results = []
        for name, test_func in tests:
            try:
                result = test_func(client)
                results.append((name, result))
                time.sleep(0.5)  # Small delay between tests
            except Exception as e:
                print(f"✗ Test error: {e}")
                results.append((name, False))
        
        # Print summary
        print_header("TEST SUMMARY")
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status:8} {name}")
        
        print("-" * 70)
        print(f"Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n✓ ALL TESTS PASSED!")
        else:
            print(f"\n✗ {total - passed} test(s) failed")
        
        return 0 if passed == total else 1
    
    finally:
        client.disconnect()


if __name__ == "__main__":
    sys.exit(main())
