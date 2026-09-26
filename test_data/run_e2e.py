import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
PY = str(ROOT / "venv" / "Scripts" / "python.exe")

print("[*] Starting backend on port 8000...")
proc = subprocess.Popen(
    [PY, "-m", "uvicorn", "main:app", "--port", "8000"],
    cwd=str(BACKEND)
)

try:
    print("[*] Waiting for backend to be ready at http://localhost:8000/api/health...")
    ready = False
    for _ in range(25):
        try:
            with urllib.request.urlopen("http://localhost:8000/api/health", timeout=2) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            pass
        time.sleep(1)

    if not ready:
        print("[!] Backend failed to start within timeout.")
        sys.exit(1)

    print("[*] Backend is ready! Running e2e_smoke.py...")
    ret = subprocess.run([PY, str(ROOT / "test_data" / "e2e_smoke.py")], cwd=str(ROOT))
    print(f"[*] e2e_smoke finished with exit code {ret.returncode}")
finally:
    print("[*] Terminating backend process...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("[*] Backend terminated cleanly.")
