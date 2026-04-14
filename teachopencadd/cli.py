import os
import shutil
import re
import sys
import glob
import json
import argparse
import nbformat
import subprocess
import requests
import logging
from pathlib import Path

from rich import print
from rich.logging import RichHandler
from rich.panel import Panel
from rich.prompt import Confirm
from rich.progress import track
from rich.console import Console

console = Console()

ENV_PREFIX = "teachopencadd"
BASE_DIR = Path("teachopencadd") / "talktorials"
UV_ENV_ROOT = Path.home() / ".teachopencadd_envs"
REQ_FILE = "requirements.txt"
TALKTORIAL_FILE = "talktorial.ipynb"
IS_WIN = sys.platform.startswith("win")
REPO_OWNER = "volkamerlab"
REPO_NAME = "teachopencadd"
BRANCH = "dev"
API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}"
API_ROOT_PATH = "teachopencadd/talktorials/"
EXCLUDE_FILES = [".gitignore"]
ARROW = "->" if IS_WIN else "→"
CROSS = "X" if IS_WIN else "✖"


def print_err(message):
    console.print(f"[bold red]{CROSS} Error:[/bold red] {message}")


def print_step(message):
    console.print(Panel.fit(f"[bold]{message}[/bold]"))


def print_status(message):
    console.print(f"[bold blue]{ARROW}[/bold blue] {message}")


def print_warn(message):
    console.print(f"[bold yellow]{ARROW}[/bold yellow] {message}")


def run_command(command, **kwargs):
    """Wrapper for subprocess with better error reporting."""
    kwargs.setdefault("capture_output", False)
    kwargs.setdefault("text", True)

    cmd_str = " ".join(map(str, command))

    print_status(f"Run '{cmd_str}'")

    try:
        result = subprocess.run(command, shell=IS_WIN, **kwargs)
    except FileNotFoundError:
        print_err(f"Command not found: {command[0]}")
        sys.exit(1)

    if result.returncode != 0:
        console.print(
            Panel(cmd_str, title="[red]Command Failed[/red]", border_style="red")
        )
        if result.stdout:
            console.print(Panel(result.stdout, title="stdout", border_style="yellow"))
        if result.stderr:
            console.print(Panel(result.stderr, title="stderr", border_style="red"))
        if kwargs.get("check", False):
            sys.exit(result.returncode)

    return result


def get_conda_bin():
    """Finds micromamba or conda executable."""
    for bin_name in ["micromamba", "mamba", "conda"]:
        path = shutil.which(bin_name)
        if path:
            return path
    print_err("Could not find micromamba/mamba/conda. Please install one.")
    sys.exit(1)


def parse_requirements(req_file):
    """
    Parses talktorial requirements.
    Detects python version and splits packages into conda vs pip.
    Example line: 'rdkit # conda'
    """
    py_version = "3.11"
    conda_pkgs, pip_pkgs = [], []

    py_pattern = re.compile(r"#python\s*[=:]\s*([\d\.]+)", re.IGNORECASE)
    conda_tag = re.compile(r"^([^#]+)\s*#\s*conda\b", re.IGNORECASE)

    if not Path(req_file).exists():
        return py_version, [], []

    with open(req_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if match := py_pattern.search(line):
                py_version = match.group(1)
                continue

            if line.startswith("#"):
                continue

            if match := conda_tag.match(line):
                conda_pkgs.append(match.group(1).strip())
            else:
                pkg = line.split("#")[0].strip()
                if pkg:
                    pip_pkgs.append(pkg)

    return py_version, conda_pkgs, pip_pkgs


def get_env_info(env_name, is_conda):
    """Returns (python_exe_path, bin_dir_path)."""
    env_path = UV_ENV_ROOT / env_name

    if IS_WIN:
        py_exe = (
            env_path / "python.exe" if is_conda else env_path / "Scripts/python.exe"
        )
        bin_dir = py_exe.parent
    else:
        py_exe = env_path / "bin/python"
        bin_dir = env_path / "bin"

    return py_exe, bin_dir


def configure_env(t_id, req_file):
    """Creates the environment (UV or Conda) and returns (env_name, is_conda)."""
    print_step("Environment setup")
    py_ver, conda_pkgs, pip_pkgs = parse_requirements(req_file)
    env_name = f"{ENV_PREFIX}_{t_id}_py{py_ver.replace('.', '')}"
    env_path = UV_ENV_ROOT / env_name

    is_conda = len(conda_pkgs) > 0

    if not is_conda:
        print_status(
            f"[Pip/UV Mode] No conda dependencies. Building venv for {t_id}..."
        )
        if not env_path.exists():
            UV_ENV_ROOT.mkdir(parents=True, exist_ok=True)
            run_command(["uv", "venv", str(env_path), "--python", py_ver])

        py_exe, _ = get_env_info(env_name, is_conda=False)
        if pip_pkgs:
            run_command(["uv", "pip", "install", "--python", str(py_exe), *pip_pkgs])
    else:
        print_status(
            f"[Conda Mode] Conda dependencies found. Using solver for {t_id}..."
        )
        conda = get_conda_bin()
        mamba_root = UV_ENV_ROOT / ".mamba_cache"
        mamba_root.mkdir(exist_ok=True, parents=True)

        env_vars = {**os.environ, "MAMBA_ROOT_PREFIX": str(mamba_root)}

        run_command(
            [
                conda,
                "create",
                "-p",
                str(env_path),
                f"python={py_ver}",
                "-c",
                "conda-forge",
                "--yes",
            ],
            env=env_vars,
        )

        if conda_pkgs:
            run_command(
                [
                    conda,
                    "install",
                    "-p",
                    str(env_path),
                    "-c",
                    "conda-forge",
                    *conda_pkgs,
                    "--yes",
                ],
                env=env_vars,
            )

        py_exe, _ = get_env_info(env_name, is_conda=True)
        if pip_pkgs:
            run_command(["uv", "pip", "install", "--python", str(py_exe), *pip_pkgs])

    return env_name, is_conda


def setup_jupyter(env_name, is_conda, talktorial_path):
    """Ensures ipykernel is installed and notebook metadata is updated."""
    py_exe, _ = get_env_info(env_name, is_conda)

    print_status(f"Registering Jupyter kernel for {env_name}...")
    run_command(["uv", "pip", "install", "--python", str(py_exe), "ipykernel"])
    run_command(
        [
            str(py_exe),
            "-m",
            "ipykernel",
            "install",
            "--user",
            "--name",
            env_name,
            "--display-name",
            f"TeachOpenCADD: {env_name}",
        ]
    )

    nb = nbformat.read(talktorial_path, as_version=4)
    nb.metadata.kernelspec = {
        "name": env_name,
        "display_name": f"TeachOpenCADD: {env_name}",
        "language": "python",
    }
    nbformat.write(nb, talktorial_path)


def github_get(api_url, params=None, timeout=15):
    """Perform an unauthenticated GET to the GitHub API. Raises on non-200."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "teachopencadd-runner",
    }

    if "GITHUB_TOKEN" in os.environ:
        headers["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"

    try:
        r = requests.get(api_url, headers=headers, params=params, timeout=timeout)
    except requests.RequestException as e:
        raise SystemExit(f"Network error while accessing {api_url}: {e}")

    if r.status_code == 403 and "rate limit" in r.text.lower():
        raise SystemExit(
            "GitHub API rate limit reached (HTTP 403). "
            "Set the GITHUB_TOKEN environment variable to increase your limit."
        )
    if r.status_code != 200:
        raise SystemExit(f"GitHub API error {r.status_code} for {api_url}: {r.text}")
    return r.json()


def fetch_folder_contents(api_url, branch, exclude_files=None):
    """Recursively fetch a list of (path, raw_download_url) tuples."""
    params = {"ref": branch}
    items = github_get(api_url, params=params)
    file_list = []

    for item in items:
        item_type = item.get("type")
        name = item.get("name")
        path = item.get("path")
        if item_type == "file":
            if exclude_files and name in exclude_files:
                continue
            raw_url = f"{RAW_BASE}/{branch}/{path}"
            file_list.append((path, raw_url))
        elif item_type == "dir":
            dir_api_url = item.get("url")
            file_list.extend(fetch_folder_contents(dir_api_url, branch, exclude_files))
        else:
            print_status(f"Skipping unsupported type '{item_type}' at {path}")
    return file_list


def download_file(raw_url, local_path, timeout=30):
    """Download a raw file url and save it to local_path."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        r = requests.get(raw_url, timeout=timeout)
    except requests.RequestException as e:
        print_warn(f"Network error downloading {raw_url}: {e}")
        return False
    if r.status_code == 200:
        with open(local_path, "wb") as fh:
            fh.write(r.content)
        return True
    else:
        print_err(f"Failed to download {raw_url} (HTTP {r.status_code})")
        return False


def fetch_talktorial(t_id, data_only=False):
    """
    Main entry point for the runner. Finds the full folder name for t_id,
    downloads it if missing, and returns the local Path object.
    """
    if data_only:
        print_step("Download talktorial data")
    else:
        print_step("Ensuring talktorial contents are available")
    from pathlib import Path

    existing = list(Path(".").glob(f"{t_id}_*"))
    if existing:
        return existing[0]

    print_status(f"{t_id} not found locally. Querying GitHub API...")

    root_url = API_BASE + API_ROOT_PATH.rstrip("/")
    root_contents = github_get(root_url, params={"ref": BRANCH})

    target_folder_name = None
    for item in root_contents:
        if item["type"] == "dir" and item["name"].startswith(f"{t_id}_"):
            target_folder_name = item["name"]
            break

    if not target_folder_name:
        raise SystemExit(
            f"Error: Could not find a talktorial matching '{t_id}' on GitHub."
        )

    api_root_with_path = API_BASE + API_ROOT_PATH + target_folder_name
    output_dir = "." if data_only else target_folder_name
    os.makedirs(output_dir, exist_ok=True)

    print_status(
        f"Fetching file list for '{target_folder_name}' from branch '{BRANCH}'..."
    )
    exclude_files = EXCLUDE_FILES
    if data_only:
        exclude_files += ["README.md", "talktorial.ipynb"]
    all_files = fetch_folder_contents(
        api_root_with_path, BRANCH, exclude_files=exclude_files
    )
    print_status(f"Found {len(all_files)} files to download.")

    for path, raw_url in track(all_files, description="Downloading files..."):
        rel_local = os.path.relpath(path, API_ROOT_PATH + target_folder_name)
        local_path = os.path.join(output_dir, rel_local)

        if os.path.exists(local_path):
            try:
                if os.path.getsize(local_path) > 0:
                    continue
            except OSError:
                pass

        download_file(
            raw_url,
            local_path,
        )

    print_status(f"Done. Files saved to: ./{output_dir}")
    return Path(output_dir)


def cleanup(force=False):
    """
    Removes managed environments and unregisters their Jupyter kernels.
    Defaults to interactive mode unless force=True.
    """
    print_step("Environment cleanup")
    if not UV_ENV_ROOT.exists():
        print_status(f"No environment directory found at {UV_ENV_ROOT}.")
        return

    pattern = re.compile(rf"^{ENV_PREFIX}_T\d{{3}}_")
    envs = [d for d in UV_ENV_ROOT.iterdir() if d.is_dir() and pattern.match(d.name)]

    if not envs:
        print_status("No managed environments found.")
        return

    print_status(f"Found {len(envs)} environments in {UV_ENV_ROOT}.")

    for env_path in envs:
        env_name = env_path.name

        if not force:
            if not Confirm.ask(f"Remove environment '{env_name}'?"):
                continue

        print_status(f"Unregistering kernel: {env_name}...")
        try:
            run_command(
                ["jupyter", "kernelspec", "uninstall", env_name.lower(), "-y"],
            )
        except Exception as e:
            print_warn(f"Could not unregister kernel (may not exist): {e}")

        print_status(f"Deleting folder: {env_path}...")
        try:
            shutil.rmtree(env_path)
        except Exception as e:
            print_err(f"Error deleting folder: {e}")

    mamba_cache = UV_ENV_ROOT / "mamba_cache"
    if mamba_cache.exists():
        if force or Confirm("Clear Mamba package cache?"):
            print_status("Clearing cache...")
            shutil.rmtree(mamba_cache)

    print_status("Cleanup complete.")


def test_talktorial(talktorial_dir: Path, py_exe: Path, bin_dir: Path):
    """Installs testing dependencies and runs nbval on the notebook."""
    talktorial = talktorial_dir / TALKTORIAL_FILE
    if not talktorial.exists():
        print(f"Error: Could not find {talktorial} for testing.")
        sys.exit(1)

    print_step(f"Testing talktorial {talktorial}...")

    install_cmd = ["uv", "pip", "install", "--python", str(py_exe), "pytest", "nbval"]
    run_command(install_cmd)

    test_env = os.environ.copy()
    test_env["PATH"] = f"{bin_dir}{os.pathsep}{test_env.get('PATH', '')}"

    if not IS_WIN:
        lib_dir = str(bin_dir.parent / "lib")
        test_env["LD_LIBRARY_PATH"] = (
            f"{lib_dir}{os.pathsep}{test_env.get('LD_LIBRARY_PATH', '')}"
        )

    print_status("Running pytest with nbval...\n")
    run_command(
        [str(py_exe), "-m", "pytest", "--nbval-lax", "--current-env", str(talktorial)],
        env=test_env,
        capture_output=False,
    )


def main():
    parser = argparse.ArgumentParser(description="TeachOpenCADD Talktorial Runner")
    parser.add_argument(
        "talktorial", nargs="?", help="Talktorial ID to run (e.g., T001 or 1)"
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Remove talktorial environments"
    )
    parser.add_argument(
        "--force", action="store_true", help="Skip confirmation (cleanup)"
    )
    parser.add_argument(
        "--download-data", action="store_true", help="Download data for talktorial"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run nbval tests instead of starting Jupyter",
    )
    args = parser.parse_args()

    if args.cleanup:
        cleanup(args.force)
        return

    if not args.talktorial:
        parser.print_help()
        return

    t_num = str(args.talktorial).lower().lstrip("t").split("_")[0]
    try:
        t_id = f"T{int(t_num):03d}"
    except ValueError:
        print_err(f"Invalid talktorial ID: '{args.talktorial}'")
        return 1

    if args.download_data:
        fetch_talktorial(t_id, data_only=True)
        return

    BASE_DIR = Path("teachopencadd") / "talktorials"
    matches = list(BASE_DIR.glob(f"{t_id}_*")) if BASE_DIR.exists() else []

    if not matches:
        print_warn(f"Could not find folder for {t_id} locally. Fetching from Github...")
        t_dir = fetch_talktorial(t_id)
    else:
        t_dir = matches[0]

    req_file = t_dir / REQ_FILE
    nb_file = t_dir / TALKTORIAL_FILE
    env_name, is_conda = configure_env(t_id, req_file)
    py_exe, bin_dir = get_env_info(env_name, is_conda)

    if args.test:
        test_talktorial(t_dir, py_exe, bin_dir)
        return

    run_command(
        [str(py_exe), "-m", "ipykernel", "install", "--user", "--name", env_name],
    )

    nb = nbformat.read(nb_file, as_version=4)
    nb.metadata.kernelspec = {
        "name": env_name,
        "display_name": f"TeachOpenCADD: {env_name}",
        "language": "python",
    }
    nbformat.write(nb, nb_file)

    jupyter_bin = bin_dir / ("jupyter.exe" if IS_WIN else "jupyter")
    if not jupyter_bin.exists():
        print_err(f"Error: Jupyter binary not found at {jupyter_bin}")
        sys.exit(1)

    env_vars = os.environ.copy()
    env_vars["PATH"] = f"{bin_dir}{os.pathsep}{env_vars.get('PATH', '')}"

    if is_conda:
        env_vars["CONDA_PREFIX"] = str(bin_dir.parent)
        env_vars["MAMBA_ROOT_PREFIX"] = str(UV_ENV_ROOT / ".mamba_cache")

    print_step(f"Starting {t_id}...")
    run_command(
        [str(jupyter_bin), "notebook", str(nb_file)],
        env=env_vars,
        capture_output=False,
    )


if __name__ == "__main__":
    main()
