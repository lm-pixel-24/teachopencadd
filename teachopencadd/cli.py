import os
import shutil
import re
import sys
import glob
import json
import argparse
import nbformat
import subprocess
from pathlib import Path

ENV_PREFIX = "teachopencadd"
BASE_DIR = Path("teachopencadd") / "talktorials"
UV_ENV_ROOT = Path.home() / ".teachopencadd_envs"
REQ_FILE = "requirements.txt"
TALKTORIAL_FILE = "talktorial.ipynb"
IS_WIN = sys.platform.startswith("win")


def run_command(command, verbose=True, **kwargs):
    """Wrapper for subprocess with better error reporting."""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)

    try:
        result = subprocess.run(command, shell=IS_WIN, **kwargs)
    except FileNotFoundError as e:
        print(f"Error: Could not find command '{command[0]}'. Is it installed?")
        sys.exit(1)

    if result.returncode != 0:
        print("\n" + "!" * 60)
        print(f"Command Failed: {' '.join(map(str, command))}")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("!" * 60)
        sys.exit(result.returncode)

    if verbose and result.stdout.strip():
        print(result.stdout)
    return result


def get_conda_bin():
    """Finds micromamba or conda executable."""
    for bin_name in ["micromamba", "mamba", "conda"]:
        path = shutil.which(bin_name)
        if path:
            return path
    print("Error: Could not find micromamba/mamba/conda. Please install one.")
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
    py_ver, conda_pkgs, pip_pkgs = parse_requirements(req_file)
    env_name = f"{ENV_PREFIX}_{t_id}_py{py_ver.replace('.', '')}"
    env_path = UV_ENV_ROOT / env_name

    is_conda = len(conda_pkgs) > 0

    if not is_conda:
        print(f"🚀 [UV Mode] No conda dependencies. Building venv for {t_id}...")
        if not env_path.exists():
            UV_ENV_ROOT.mkdir(parents=True, exist_ok=True)
            run_command(["uv", "venv", str(env_path), "--python", py_ver])

        py_exe, _ = get_env_info(env_name, is_conda=False)
        if pip_pkgs:
            run_command(["uv", "pip", "install", "--python", str(py_exe), *pip_pkgs])
    else:
        print(f"📦 [Conda Mode] Conda dependencies found. Using solver for {t_id}...")
        conda = get_conda_bin()
        mamba_root = UV_ENV_ROOT / ".mamba_cache"
        mamba_root.mkdir(exist_ok=True)

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

    print(f"Registering Jupyter kernel for {env_name}...")
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


def cleanup(force=False):
    """
    Removes managed environments and unregisters their Jupyter kernels.
    Defaults to interactive mode unless force=True.
    """
    if not UV_ENV_ROOT.exists():
        print(f"No environment directory found at {UV_ENV_ROOT}.")
        return

    pattern = re.compile(rf"^{ENV_PREFIX}_T\d{{3}}_")
    envs = [d for d in UV_ENV_ROOT.iterdir() if d.is_dir() and pattern.match(d.name)]

    if not envs:
        print("No managed environments found.")
        return

    print(f"Found {len(envs)} environments in {UV_ENV_ROOT}.\n")

    for env_path in envs:
        env_name = env_path.name

        if not force:
            choice = input(f"Remove environment '{env_name}'? [y/N]: ").lower()
            if choice != "y":
                continue

        print(f"  - Unregistering kernel: {env_name}...")
        try:
            subprocess.run(
                ["jupyter", "kernelspec", "uninstall", env_name.lower(), "-y"],
                capture_output=False,
                text=True,
                check=False,
            )
        except Exception as e:
            print(f"    ! Note: Could not unregister kernel (may not exist): {e}")

        print(f"  - Deleting folder: {env_path}...")
        try:
            shutil.rmtree(env_path)
        except Exception as e:
            print(f"    ! Error deleting folder: {e}")

    mamba_cache = UV_ENV_ROOT / ".mamba_cache"
    if mamba_cache.exists():
        if force or input("\nClear Mamba package cache? [y/N]: ").lower() == "y":
            print("Clearing cache...")
            shutil.rmtree(mamba_cache)

    print("\nCleanup complete.")


def main():
    parser = argparse.ArgumentParser(description="TeachOpenCADD Talktorial Runner")
    parser.add_argument("talktorial", nargs="?", help="T-id to run (e.g., T001)")
    parser.add_argument(
        "--cleanup", action="store_true", help="Remove all talktorial envs"
    )
    parser.add_argument("--force", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    if args.cleanup:
        cleanup(args.force)
        return

    if not args.talktorial:
        parser.print_help()
        return

    t_num = str(args.talktorial).lower().lstrip("t").split("_")[0]
    t_id = f"T{int(t_num):03d}"

    matches = list(BASE_DIR.glob(f"{t_id}_*"))
    if not matches:
        print(f"Error: Could not find folder for {t_id} in {BASE_DIR}")
        sys.exit(1)

    t_dir = matches[0]
    req_file = t_dir / REQ_FILE
    nb_file = t_dir / TALKTORIAL_FILE

    env_name, is_conda = configure_env(t_id, req_file)
    setup_jupyter(env_name, is_conda, nb_file)

    py_exe, bin_dir = get_env_info(env_name, is_conda)
    jupyter_bin = bin_dir / ("jupyter.exe" if IS_WIN else "jupyter")
    if not jupyter_bin.exists():
        print(f"Error: Jupyter binary not found at {jupyter_bin}")
        sys.exit(1)

    env_vars = os.environ.copy()
    new_path = f"{bin_dir}{os.pathsep}{env_vars.get('PATH', '')}"
    env_vars["PATH"] = new_path

    if is_conda:
        env_vars["CONDA_PREFIX"] = str(bin_dir.parent)
        env_vars["MAMBA_ROOT_PREFIX"] = str(UV_ENV_ROOT / ".mamba_cache")

    print(f"\nStarting {t_id}...")

    run_command(
        [str(jupyter_bin), "notebook", str(nb_file)], env=env_vars, capture_output=False
    )


if __name__ == "__main__":
    main()
