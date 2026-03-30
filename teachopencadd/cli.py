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


def get_python_path(env_name):
    """
    Ask Conda exactly where the python executable is for the new env.
    This works regardless of OS or where Conda is installed.
    """
    try:
        cmd = "where python" if IS_WIN else "which python"
        conda_bin = get_conda_executable()
        result = run_command([conda_bin, "run", "-n", env_name, *cmd.split()])
        return Path(result.stdout.strip().splitlines()[0])
    except subprocess.CalledProcessError:
        controlled_crash(f"Conda created '{env_name}' but it has no python binary.")


def configure_env(prefix, python_version, req_file, verbose=False):
    env_name = f"{prefix}_{python_version.replace('.', '')}"
    conda_bin = get_conda_executable()
    root_prefix = get_conda_root()
    print(root_prefix)

    base_cmd = [conda_bin]
    print(conda_bin, "micromamba" in conda_bin)
    if "micromamba" in conda_bin.lower():
        base_cmd += ["-r", root_prefix]
    print(base_cmd)

    print(
        f"Creating environment '{env_name}' using {conda_bin} with Python {python_version} in {root_prefix}"
    )
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
                conda_bin,
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


def conda_env_list():
    """
    List all conda environments.
    returns:
        list: List of conda environment names.
    """
    conda_bin = get_conda_executable()
    result = run_command(
        [conda_bin, "env", "list"],
    )

    envs = result.stdout.splitlines()
    return [line.split()[0] for line in envs if line and not line.startswith("#")]


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
    if talktorial.exists():
        print(f"Starting talktorial {talktorial}")
        notebook_cmd = f"conda run -n {env_name} jupyter notebook {str(talktorial)}"
        run_command(notebook_cmd, shell=True)
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


def parse_talktorial(ident):
    ident = int(str(ident).lstrip("T0").partition("_")[0])
    return "T{0:03}".format(ident)


def main():
    parser = argparse.ArgumentParser(description="CLI.")
    parser.add_argument(
        "talktorial",
        help="Taltorial to run, e.g., T001 or 1",
    )
    parser.add_argument(
        "--test", action="store_true", help="Test the talktorial using pytest."
    )
    args = parser.parse_args()
    run(parse_talktorial(args.talktorial), args.test)


if __name__ == "__main__":
    main()
