import os
import sys
import venv
import subprocess
import glob
import shutil
from pathlib import Path

HERE = Path(".").absolute()
BASE_DIR = Path("teachopencadd") / "talktorials"
REQ_FILE = "requirements.txt"
VENV_DIR = ".venv"
TALKTORIAL_FILE = "talktorial.ipynb"


def find_talktorial_folder(txxx):
    search_pattern = HERE / BASE_DIR / f"{txxx}_*"
    matches = glob.glob(str(search_pattern))

    if not matches:
        controlled_crash(f"No folder found for '{txxx}_*' in '{BASE_DIR}'.")

    return Path(matches[0])


def install_dependencies(talktorial_dir):
    req_path = talktorial_dir / REQ_FILE
    if req_path.exists():
        print(f"Installing dependencies in {talktorial_dir}")
        pip(f"install -r {req_path}", talktorial_dir)
    else:
        print(
            f"Warning: '{req_path}' not found. Skipping dependency installation.",
            file=sys.stderr,
        )


def has_uv():
    return shutil.which("uv") is not None


def call(command, talktorial_dir, **kwargs):
    local_env = os.environ.copy()
    local_env = {
        k: v for k, v in local_env.items() if ("CONDA" not in k and "FORGE" not in k)
    }
    # probably different on windows...
    local_env["PATH"] = str(talktorial_dir / VENV_DIR / "bin") + ":" + local_env["PATH"]

    match str(type(command)):
        case "<class 'str'>":
            command = command.split()
        case "<class 'list'>":
            pass
        case ty:
            raise ValueError(f"unexpected command {command} with type {ty}")

    print(" ".join(command))
    return subprocess.run(
        command,
        cwd=talktorial_dir,
        env=local_env,
        check=True,
        capture_output=True,
        **kwargs,
    )


def pip(command, talktorial_dir):
    """Run pip (or uv if available) in the venv."""
    command = command.split()
    if has_uv():
        base_cmd = ["uv", "pip"]
    else:
        pyexec = python_executable(talktorial_dir)
        base_cmd = [pyexec, "-m", "pip"]

    call(base_cmd + command, talktorial_dir)


def python_executable(talktorial_dir: Path):
    """Return the path to the Python interpreter inside the virtual environment."""
    return str(
        talktorial_dir
        / VENV_DIR
        / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )


def create_venv(talktorial_dir: Path):
    """Create a virtual environment if it doesn't exist."""
    venv_path = talktorial_dir / VENV_DIR
    if not venv_path.exists():
        print(f"Creating virtual environment in '{venv_path}'...")
        venv.create(venv_path, with_pip=True)


def ensure_jupyter_kernel(talktorial_dir: Path, kernel_name: str):
    """Ensure Jupyter and the correct kernel are installed inside the virtual environment."""
    print("Ensuring Jupyter and ipykernel are installed inside venv...")
    pip("install jupyter ipykernel", talktorial_dir)

    # Register the virtual environment as a Jupyter kernel
    pyexec = python_executable(talktorial_dir)
    try:
        call(
            [
                pyexec,
                "-m",
                "ipykernel",
                "install",
                "--user",
                "--name",
                kernel_name,
                "--display-name",
                f"Python (venv {kernel_name})",
            ],
            talktorial_dir,
        )
    except subprocess.CalledProcessError as e:
        controlled_crash(e.stderr.decode())


def start_talktorial(talktorial_dir: Path, talktorial_id: str):
    """Start the Jupyter Notebook inside the correct virtual environment."""
    talktorial = talktorial_dir / TALKTORIAL_FILE
    if talktorial.exists():
        print(f"Starting talktorial {talktorial}")
        pyexec = python_executable(talktorial_dir)

        ensure_jupyter_kernel(talktorial_dir, talktorial_id)

        res = call(
            "jupyter notebook talktorial.ipynb",
            talktorial_dir,
        )
    else:
        controlled_crash(f"Error: Notebook '{talktorial}' not found.")


def controlled_crash(reason, code=1):
    """Print an error message and exit."""
    print("Error: " + reason, file=sys.stderr)
    sys.exit(code)


def main():
    if len(sys.argv) != 2:
        controlled_crash("Usage: python start_talktorial.py TXXX")

    txxx = sys.argv[1]

    if not (txxx.startswith("T") and txxx[1:].isdigit() and len(txxx) == 4):
        controlled_crash(
            "Argument must be in the format TXXX (e.g., T001, T023, T030)."
        )

    talktorial_dir = find_talktorial_folder(txxx)

    create_venv(talktorial_dir)
    install_dependencies(talktorial_dir)
    start_talktorial(talktorial_dir, txxx)


if __name__ == "__main__":
    main()
