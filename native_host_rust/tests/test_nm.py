#!/usr/bin/env python3
"""
Native Messaging Test Script for winocr_host
Tests the NM communication protocol via stdin/stdout

Usage:
    python tests/test_nm.py [path_to_winocr_host.exe]

Example:
    python tests/test_nm.py ../target/debug/winocr_host.exe
    python tests/test_nm.py --standalone  # Run host directly
"""

import json
import struct
import subprocess
import sys
import time
import os

# NM protocol constants
NM_MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB


def send_message(proc, msg_dict):
    """Send a NM message to the process"""
    data = json.dumps(msg_dict).encode("utf-8")
    length = struct.pack("<I", len(data))
    proc.stdin.write(length + data)
    proc.stdin.flush()
    print(f"[SENT] {msg_dict}")


def read_message(proc):
    """Read a NM response from the process"""
    length_bytes = proc.stdout.read(4)
    if not length_bytes or len(length_bytes) < 4:
        return None
    length = struct.unpack("<I", length_bytes)[0]
    if length > NM_MAX_MESSAGE_SIZE:
        raise ValueError(f"Message too large: {length} bytes")
    data = proc.stdout.read(length)
    if len(data) < length:
        return None
    return json.loads(data.decode("utf-8"))


def test_version(proc):
    """Test GetVersion message"""
    print("\n=== Test 1: GetVersion ===")
    send_message(proc, {"type": "get_version"})
    resp = read_message(proc)
    print(f"[RECV] {resp}")
    assert resp is not None, "No response received"
    assert resp.get("type") == "version", f"Expected 'version', got {resp.get('type')}"
    print("PASS: Version info received")
    return resp


def test_init(proc):
    """Test Init message"""
    print("\n=== Test 2: Init ===")
    send_message(proc, {
        "type": "init",
        "extension_version": "1.0.0"
    })
    resp = read_message(proc)
    print(f"[RECV] {resp}")
    assert resp is not None, "No response received"
    assert resp.get("type") == "init_ack", f"Expected 'init_ack', got {resp.get('type')}"
    assert resp.get("success") is True, "Init should succeed"
    print("PASS: Init acknowledged")
    return resp


def test_translate(proc):
    """Test Translate message"""
    print("\n=== Test 3: Translate ===")
    send_message(proc, {
        "type": "translate",
        "text": "Hello World",
        "source_lang": "en",
        "target_lang": "zh"
    })
    resp = read_message(proc)
    print(f"[RECV] {resp}")
    assert resp is not None, "No response received"
    assert resp.get("type") == "translate", f"Expected 'translate', got {resp.get('type')}"
    print("PASS: Translation received")
    return resp


def test_ping(proc):
    """Test Ping message"""
    print("\n=== Test 4: Ping ===")
    send_message(proc, {
        "type": "ping",
        "timestamp": int(time.time())
    })
    resp = read_message(proc)
    print(f"[RECV] {resp}")
    assert resp is not None, "No response received"
    assert resp.get("type") == "pong", f"Expected 'pong', got {resp.get('type')}"
    print("PASS: Pong received")
    return resp


def test_get_settings(proc):
    """Test GetSettings message"""
    print("\n=== Test 5: GetSettings ===")
    send_message(proc, {"type": "get_settings"})
    resp = read_message(proc)
    print(f"[RECV] {resp}")
    assert resp is not None, "No response received"
    assert resp.get("type") == "settings", f"Expected 'settings', got {resp.get('type')}"
    print("PASS: Settings received")
    return resp


def test_unknown(proc):
    """Test Unknown message type"""
    print("\n=== Test 6: Unknown message ===")
    send_message(proc, {"type": "unknown_type", "data": "test"})
    resp = read_message(proc)
    print(f"[RECV] {resp}")
    assert resp is not None, "No response received"
    assert resp.get("type") == "error", f"Expected 'error', got {resp.get('type')}"
    print("PASS: Error response for unknown type")
    return resp


def run_tests(host_path):
    """Run all NM tests"""
    print(f"Starting NM tests with host: {host_path}")
    print("=" * 60)

    # Start host process
    try:
        proc = subprocess.Popen(
            [host_path, "--standalone"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(host_path)
        )
    except FileNotFoundError:
        print(f"ERROR: Host executable not found at {host_path}")
        return False

    try:
        # Give host time to initialize
        time.sleep(0.5)

        # Run tests
        results = []

        results.append(("GetVersion", test_version(proc)))
        results.append(("Init", test_init(proc)))
        results.append(("Ping", test_ping(proc)))
        results.append(("Translate", test_translate(proc)))
        results.append(("GetSettings", test_get_settings(proc)))
        results.append(("Unknown", test_unknown(proc)))

        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        for name, resp in results:
            status = "PASS" if resp is not None else "FAIL"
            print(f"  [{status}] {name}")

        # Check if all tests passed
        all_passed = all(resp is not None for _, resp in results)
        if all_passed:
            print("\nAll tests PASSED!")
        else:
            print("\nSome tests FAILED!")

        return all_passed

    except Exception as e:
        print(f"\nERROR during tests: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)
        print("\nHost process terminated")


def interactive_mode(host_path):
    """Run in interactive mode - send custom messages"""
    print(f"Starting interactive NM test with host: {host_path}")
    print("Enter JSON messages (one per line), or 'quit' to exit")
    print("Example: {\"type\": \"get_version\"}")
    print("-" * 60)

    try:
        proc = subprocess.Popen(
            [host_path, "--standalone"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(host_path)
        )
    except FileNotFoundError:
        print(f"ERROR: Host executable not found at {host_path}")
        return

    try:
        time.sleep(0.5)

        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break

            if not line:
                continue
            if line.lower() == "quit":
                break

            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Invalid JSON: {e}")
                continue

            try:
                send_message(proc, msg)
                resp = read_message(proc)
                if resp:
                    print(f"< {json.dumps(resp, indent=2, ensure_ascii=False)}")
                else:
                    print("< No response")
            except Exception as e:
                print(f"Error: {e}")

    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)
        print("\nHost process terminated")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Native Messaging Test Script")
    parser.add_argument(
        "host_path",
        nargs="?",
        default=None,
        help="Path to winocr_host.exe"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build the host first"
    )

    args = parser.parse_args()

    # Determine host path
    host_path = args.host_path
    if host_path is None:
        # Default paths to try
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(script_dir)
        default_paths = [
            os.path.join(project_dir, "target", "debug", "winocr_host.exe"),
            os.path.join(project_dir, "target", "release", "winocr_host.exe"),
        ]
        for path in default_paths:
            if os.path.exists(path):
                host_path = path
                break

        if host_path is None:
            print("ERROR: Could not find winocr_host.exe")
            print("Please build the project first: cargo build")
            print("Or specify the path explicitly")
            sys.exit(1)

    # Build if requested
    if args.build:
        print("Building host...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(script_dir)
        result = subprocess.run(
            ["cargo", "build"],
            cwd=project_dir
        )
        if result.returncode != 0:
            print("Build failed!")
            sys.exit(1)
        print("Build complete!")

    # Run tests
    if args.interactive:
        interactive_mode(host_path)
    else:
        success = run_tests(host_path)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
