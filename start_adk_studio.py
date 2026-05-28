import os
import sys
import subprocess
import platform
import time

def print_banner():
    print("==============================================================")
    print("🌌  Hubscape ADK Studio - Holodeck Launch Sequence")
    print("==============================================================")
    print(f"Detecting OS: {platform.system()} ({platform.release()})")

def setup_virtualenv(venv_dir, python_executable):
    """Creates a virtual environment and installs dependencies if missing."""
    if not os.path.exists(venv_dir):
        print("\n⚙️  No virtual environment found. Initializing 'venv'...")
        try:
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
            print("✅ Virtual environment created successfully.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create virtual environment: {e}")
            sys.exit(1)

    # Resolve pip path
    pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe") if platform.system() == "Windows" else os.path.join(venv_dir, "bin", "pip")
    
    # Check if packages are installed by trying to import hubscape_adk
    try:
        # Run a quick check using the venv python to see if package is installed and importable
        subprocess.run([python_executable, "-c", "import fastapi, uvicorn, pydantic, google.genai, hubscape_adk"], 
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ Package and dependencies verified.")
    except subprocess.CalledProcessError:
        print("\n📥 Installing/updating required package and dependencies in editable mode...")
        try:
            subprocess.run([pip_exe, "install", "--upgrade", "pip"], check=True)
            subprocess.run([pip_exe, "install", "-e", "."], check=True)
            print("✅ Package and dependencies installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install package: {e}")
            sys.exit(1)

def start_server(python_executable):
    """Launches the sandbox server as a module using the virtual environment's Python."""
    print("\n🚀 Starting Holodeck Sandbox Server...")
    print("   Press CTRL+C to terminate the server.\n")
    
    try:
        # Add project root to PYTHONPATH to ensure package imports resolve
        script_dir = os.path.dirname(os.path.abspath(__file__))
        env = os.environ.copy()
        env["PYTHONPATH"] = script_dir + os.pathsep + env.get("PYTHONPATH", "")
        
        cmd = [python_executable, "-m", "hubscape_adk.run_sandbox"]
        cwd = os.getcwd()
        # Fallback to example agent folder if config.json is missing in root
        if not os.path.exists("config.json") and os.path.exists(os.path.join("example", "config.json")):
            print("ℹ️  No local config found in root. Booting in Example Agent mode...")
            cwd = os.path.join(cwd, "example")
            
        subprocess.run(cmd, cwd=cwd, env=env)
    except KeyboardInterrupt:
        print("\n🛑 Holodeck Server shut down by user.")
    except Exception as e:
        print(f"❌ Error starting server: {e}")

def main():
    print_banner()
    
    # Determine directory paths relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    venv_dir = os.path.join(script_dir, "venv")
    
    # Resolve the virtual environment python executable
    if platform.system() == "Windows":
        python_executable = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        python_executable = os.path.join(venv_dir, "bin", "python")
        
    # Step 1: Ensure virtualenv and dependencies are prepped
    setup_virtualenv(venv_dir, python_executable)
    
    # Step 2: Start the server
    start_server(python_executable)

if __name__ == "__main__":
    main()
