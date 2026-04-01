import os
import shutil
import re
import sys
import glob
import argparse
import nbformat
import subprocess
from pathlib import Path

BASE_DIR = Path("teachopencadd") / "talktorials"
REQ_FILE = "requirements.txt"
TALKTORIAL_FILE = "talktorial.ipynb"
IS_WIN = "win32" in str(sys.platform.lower())
ENV_PREFIX = "teachopencadd_"
PROJECT_URL = "https://projects.volkamerlab.org/teachopencadd"


def run_command(command, verbose=True, **kwargs):
    kwargs |= dict(shell=False, capture_output=True, text=True)
    result = subprocess.run(command, **kwargs)
    if result.returncode != 0:
        print("\n" + "=" * 50)
        print(f"!!! Command {' '.join(command)} failed !!!")
        print("=" * 50)
        print("STDOUT:\n", result.stdout)
        print("-" * 20)
        print("STDERR:\n", result.stderr)
        print("=" * 50)
        sys.exit(result.returncode)

    if verbose:
        print(result.stdout)
    return result


def package_info(req_file):
    python_version = "3.11"  # Default fallback if not found
    conda_pkgs = []
    pip_pkgs = []

    py_pattern = re.compile(r"#python\s*[=:]\s*([\d\.]+)", re.IGNORECASE)
    conda_tag_pattern = re.compile(r"^([^#]+)\s*#\s*conda\b", re.IGNORECASE)

    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            py_match = py_pattern.search(line)
            if py_match:
                python_version = py_match.group(1)
                if line.lower().startswith("python") or line.startswith("#"):
                    if not conda_tag_pattern.search(line):
                        continue

            if line.startswith("#"):
                continue

            conda_match = conda_tag_pattern.match(line)
            if conda_match:
                conda_pkgs.append(conda_match.group(1).strip())
            else:
                pkg_name = line.split("#")[0].strip()
                if pkg_name:
                    pip_pkgs.append(pkg_name)

    return python_version, conda_pkgs, pip_pkgs


def conda_base_cmd():
    conda_bin = get_conda_executable()
    root_prefix = get_conda_root()

    base_cmd = [conda_bin]
    print(conda_bin, "micromamba" in conda_bin)
    if "micromamba" in conda_bin.lower():
        base_cmd += ["-r", root_prefix]
    return base_cmd


def get_python_path(env_name):
    """
    Ask Conda exactly where the python executable is for the new env.
    This works regardless of OS or where Conda is installed.
    """
    try:
        cmd = "where python" if IS_WIN else "which python"
        base_cmd = conda_base_cmd()
        result = run_command(base_cmd + ["run", "-n", env_name, *cmd.split()])
        return Path(result.stdout.strip().splitlines()[0])
    except subprocess.CalledProcessError:
        controlled_crash(f"Conda created '{env_name}' but it has no python binary.")


def configure_env(prefix, python_version, req_file, verbose=False):
    env_name = f"{ENV_PREFIX}_{prefix}_{python_version.replace('.', '')}"
    base_cmd = conda_base_cmd()
    run_command(
        [
            *base_cmd,
            "create",
            "-n",
            env_name,
            f"python={python_version}",
            "-c",
            "conda-forge",
            "--yes",
        ],
    )

    py_vrs, conda_pkgs, pip_pkgs = package_info(req_file)

    python_exe = str(get_python_path(env_name))
    print(f"Found dynamic python at: {python_exe}")

    if conda_pkgs:
        run_command(
            [
                *base_cmd,
                "install",
                "-n",
                env_name,
                "-c",
                "conda-forge",
                *conda_pkgs,
                "--yes",
            ],
        )

    if pip_pkgs:
        print(f"Using uv to install dependencies into {env_name}...")
        run_command(
            ["uv", "pip", "install", "--python", python_exe, *pip_pkgs],
        )

    return env_name


def set_ipykernel(env_name):
    print(f"Setting ipykernel for '{env_name}'...")
    python_exe = str(get_python_path(env_name))
    use_uv = shutil.which("uv") is not None

    install_cmd = (
        ["uv", "pip", "install", "--python", python_exe, "ipykernel"]
        if use_uv
        else [python_exe, "-m", "pip", "install", "ipykernel"]
    )

    run_command(install_cmd)

    run_command(
        [
            python_exe,
            "-m",
            "ipykernel",
            "install",
            "--user",
            "--name",
            env_name,
            "--display-name",
            env_name,
        ],
    )


def test_talktorial(talktorial_dir: Path, env_name: str):
    talktorial = talktorial_dir / TALKTORIAL_FILE
    if talktorial.exists():
        print(f"Testing talktorial {talktorial}")
        python_exe = str(get_python_path(env_name))
        use_uv = shutil.which("uv") is not None

        install_cmd = (
            ["uv", "pip", "install", "--python", python_exe, "pytest", "nbval"]
            if use_uv
            else [python_exe, "-m", "pip", "install", "pytest", "nbval"]
        )
        run_command(install_cmd, check=True, shell=IS_WIN)

        bin_dir = str(Path(python_exe).parent)
        test_env = os.environ.copy()
        test_env["PATH"] = f"{bin_dir}{os.pathsep}{test_env.get('PATH', '')}"

        if not IS_WIN:
            lib_dir = str(Path(bin_dir).parent / "lib")
            test_env["LD_LIBRARY_PATH"] = (
                f"{lib_dir}{os.pathsep}{test_env.get('LD_LIBRARY_PATH', '')}"
            )

        run_command(
            [python_exe, "-m", "pytest", "--nbval-lax", str(talktorial)],
            env=test_env,
        )


def get_conda_root():
    """Finds the path to the conda/mamba binary and the root prefix."""
    conda_bin = get_conda_executable()

    result = subprocess.run(
        [conda_bin, "info", "--json"], capture_output=True, text=True, shell=IS_WIN
    )
    import json

    data = json.loads(result.stdout)
    root_prefix = data.get("root_prefix") or data.get("base environment")

    if root_prefix == "/" or root_prefix is None:
        root_prefix = os.path.expanduser("./micromamba")
        if not os.path.exists(root_prefix):
            root_prefix = os.path.expanduser("./miniconda3")

    return root_prefix


def get_conda_executable():
    """Finds the actual path to conda or micromamba."""
    mamba = shutil.which("micromamba")
    if mamba:
        return mamba

    conda = shutil.which("conda")
    if conda:
        return conda

    possible_paths = [
        "/usr/local/bin/micromamba",
        "/Users/runner/micromamba/bin/micromamba",
        "/home/runner/micromamba/bin/micromamba",
        "C:\\Scripts\\micromamba.exe",
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p

    controlled_crash("Could not find 'conda' or 'micromamba' executable in PATH.")


def set_nb_kernelspec(talktorial_dir: Path, env_name: str):
    """
    Set the kernel spec of the notebook to match the conda env.
    """
    nb_path = talktorial_dir / TALKTORIAL_FILE
    if nb_path.exists():
        print(f"Set kernel spec for {nb_path} to {env_name}")
        nb = nbformat.read(nb_path, as_version=4)
        nb.metadata.kernelspec = {
            "name": env_name.lower(),
            "display_name": env_name,
            "language": "python",
        }
        nbformat.write(nb, nb_path)
    else:
        controlled_crash(f"Error: Notebook '{nb_path}' not found.")


def find_talktorial_folder(txxx):
    search_pattern = BASE_DIR / f"{txxx}_*"
    matches = glob.glob(str(search_pattern))
    if not matches:
        controlled_crash(
            f"No folder found for '{txxx}_*' \
                        in '{BASE_DIR}'."
        )
    return Path(matches[0])


def start_talktorial(talktorial_dir: Path, env_name: str):
    """Start the Jupyter Notebook inside the correct conda environment."""
    talktorial = talktorial_dir / TALKTORIAL_FILE
    base_cmd = conda_base_cmd()

    if talktorial.exists():
        print(f"Starting talktorial {talktorial}")
        cmd = base_cmd + ["run", "-n", env_name, "jupyter", "notebook", talktorial]
        run_command(cmd, shell=True)
    else:
        controlled_crash(f"Error: Notebook '{talktorial}' not found.")


def controlled_crash(reason, code=1):
    """Print an error message and exit."""
    print("Error: " + reason, file=sys.stderr)
    sys.exit(code)


def run(txxx, test_mode=False):
    talktorial_dir = find_talktorial_folder(txxx)
    print(f"Found talktorial folder: \n{talktorial_dir}")
    req_path = talktorial_dir / REQ_FILE
    req_path = str(req_path)  # convert posixpath to str
    if not os.path.exists(req_path):
        controlled_crash(
            f"Requirements file '{REQ_FILE}' \
                            not found in {talktorial_dir}."
        )
    python_version, conda_pkgs, pip_pkgs = package_info(req_path)
    print(f"Python version: {python_version}")
    print(f"Pip package list: \n{pip_pkgs}")
    print(f"Conda package list: \n{conda_pkgs}")

    env_name = configure_env(txxx, python_version, req_path, verbose=test_mode)
    print(f"Configured environment: {env_name}")
    set_ipykernel(env_name)
    set_nb_kernelspec(talktorial_dir, env_name)

    if test_mode:
        test_talktorial(talktorial_dir, env_name)
    else:
        start_talktorial(talktorial_dir, env_name)


def teachopencadd_env_list():
    return [e for e in conda_env_list() if re.match(r"T\d{3}_", e)]


def conda_env_list():
    """
    Returns a list of tuples: (name_or_none, full_path)
    """
    base_cmd = conda_base_cmd()
    result = run_command(base_cmd + ["env", "list"], verbose=False)

    envs = []
    lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.startswith(("#", "Name", "---"))
    ]

    for line in lines:
        parts = line.split()
        if parts[0].startswith("/") or len(parts) > 1 and ":" in parts[0]:
            envs.append((None, parts[0]))
        else:
            envs.append((parts[0], parts[-1]))
    return envs


def cleanup_environments(force=False):
    """Removes all talktorial-specific environments by path or name."""
    all_envs = conda_env_list()
    to_delete = []

    pattern = re.compile(r"T\d{3}_")

    for name, path in all_envs:
        identifier = name if name else Path(path).name
        if pattern.match(identifier):
            to_delete.append((name, path))

    if not to_delete:
        print("No talktorial environments found to clean.")
        return

    print(f"Found {len(to_delete)} environments to delete:")
    for name, path in to_delete:
        print(f" - {name if name else '<unnamed>'} ({path})")

    if not force:
        confirm = input("\nDelete these environments? [y/N]: ")
        if confirm.lower() != "y":
            return

    base_cmd = conda_base_cmd()
    for name, path in to_delete:
        flag = "-n" if name else "-p"
        target = name if name else path
        print(f"Removing {target}...")
        cmd = base_cmd + ["env", "remove", flag, target]
        if force:
            cmd.append("--yes")
        subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(
        description="TeachOpenCADD: A teaching platform for computer-aided drug design (CADD) using open source packages and data.",
        epilog=f"Visit '{PROJECT_URL}' for more information.",
    )
    parser.add_argument(
        "talktorial",
        nargs="?",
        help="Taltorial to run, e.g., T001 or 1",
    )
    parser.add_argument(
        "--test", action="store_true", help="Test the talktorial using pytest"
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Remove all talktorial (TXXX_*) envs"
    )
    parser.add_argument(
        "--force", action="store_true", help="Don't ask for confirmation during cleanup"
    )
    args = parser.parse_args()
    if args.cleanup:
        cleanup_environments(force=args.force)
    elif args.talktorial:
        ident = int(str(args.talktorial).lstrip("T0").partition("_")[0])
        run("T{0:03}".format(ident), args.test)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
