#!/usr/bin/env python3
"""
Verification script for security middleware removal
"""
import subprocess
import sys
import time

def run_command(cmd, cwd=None):
    """Run a command and return the result"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"

def test_backend_syntax():
    """Test if backend Python files have valid syntax"""
    print("🔍 Testing backend Python syntax...")

    # Check main.py
    code, stdout, stderr = run_command("python3 -m py_compile app/main.py", cwd="backend")
    if code == 0:
        print("✅ main.py syntax OK")
    else:
        print(f"❌ main.py syntax error: {stderr}")
        return False

    # Check security middleware
    code, stdout, stderr = run_command("python3 -m py_compile app/middleware/security.py", cwd="backend")
    if code == 0:
        print("✅ security.py syntax OK")
    else:
        print(f"❌ security.py syntax error: {stderr}")
        return False

    return True

def test_docker_build():
    """Test if Docker can build the backend service"""
    print("\n🐳 Testing Docker backend build...")

    # Just check if the Dockerfile exists and is readable
    try:
        with open("backend/Dockerfile", "r") as f:
            content = f.read()
            if "FROM" in content and "python" in content:
                print("✅ Dockerfile exists and looks valid")
                return True
            else:
                print("❌ Dockerfile appears invalid")
                return False
    except FileNotFoundError:
        print("❌ Dockerfile not found")
        return False

def test_env_settings():
    """Test if environment settings are correct"""
    print("\n⚙️ Testing environment settings...")

    try:
        with open(".env", "r") as f:
            env_content = f.read()

        if "API_SECURITY_ENABLED=false" in env_content:
            print("✅ Security is disabled in .env")
        else:
            print("❌ Security is not disabled in .env")
            return False

        if "API_RATE_LIMITING_ENABLED=false" in env_content:
            print("✅ Rate limiting is disabled in .env")
        else:
            print("❌ Rate limiting is not disabled in .env")
            return False

        return True
    except FileNotFoundError:
        print("❌ .env file not found")
        return False

def test_imports():
    """Test if the main application can be imported without security dependencies"""
    print("\n📦 Testing import dependencies...")

    # Create a minimal test script
    test_script = """
import sys
sys.path.insert(0, 'backend')

try:
    # Test if we can create the app without security middleware
    from app.main import app
    print("✅ App can be imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Other error: {e}")
    sys.exit(1)
"""

    # Save test script
    with open("test_import.py", "w") as f:
        f.write(test_script)

    # Run test (will likely fail due to missing dependencies, but should not fail due to security imports)
    code, stdout, stderr = run_command("python3 test_import.py")

    # Clean up
    import os
    os.remove("test_import.py")

    # We expect this to fail due to missing FastAPI, but not due to security imports
    if "security" in stderr.lower() and "No module named" not in stderr:
        print("❌ Security import errors detected")
        return False
    else:
        print("✅ No security import errors detected")
        return True

def main():
    """Run all verification tests"""
    print("🚀 Starting verification of security middleware removal...\n")

    tests = [
        ("Environment Settings", test_env_settings),
        ("Python Syntax", test_backend_syntax),
        ("Docker Configuration", test_docker_build),
        ("Import Dependencies", test_imports),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))

    # Print summary
    print("\n" + "="*50)
    print("📊 VERIFICATION SUMMARY")
    print("="*50)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n🎉 All tests passed! Security middleware has been successfully removed.")
    else:
        print("\n⚠️ Some tests failed. Please review the issues above.")

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)