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


def get_python_path(env_name):
    """
    Returns the absolute path to the python executable for a given conda env
    by asking the environment itself.
    """
    try:
        # We use conda run to get the actual path of the python interpreter
        # This is more robust than guessing based on the base directory.
        result = subprocess.run(
            [
                "conda",
                "run",
                "-n",
                env_name,
                "python",
                "-c",
                "import sys; print(sys.executable)",
            ],
            capture_output=True,
            text=True,
            check=True,
            shell=IS_WIN,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        controlled_crash(
            f"Could not determine python path for environment '{env_name}'."
        )


def package_info(req_file):
    """
    Parses requirements. Separates conda-specific packages.
    Example line in requirements.txt:
    rdkit # conda
    """
    with open(req_file, "r") as f:
        lines = f.read().splitlines()

    py_vrs_line = lines[0]
    assert py_vrs_line.startswith("#python="), "First line must be #python=3.x.x"
    py_vrs = re.findall(r"[\d.]+", py_vrs_line)[0]

    conda_pkgs = []
    pip_pkgs = []

    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "# conda" in line.lower():
            conda_pkgs.append(line.split("#")[0].strip())
        else:
            pip_pkgs.append(line.split("#")[0].strip())

    return py_vrs, conda_pkgs, pip_pkgs


def configure_env(prefix, python_version, req_file, verbose=False):
    env_name = f"{prefix}_{python_version.replace('.', '')}"
    existing_envs = conda_env_list()

    # 1. Create Base Env
    if env_name not in existing_envs:
        print(f"Creating conda environment '{env_name}'...")
        subprocess.run(
            ["conda", "create", "-n", env_name, f"python={python_version}", "--yes"],
            check=True,
            shell=IS_WIN,
        )

    py_vrs, conda_pkgs, pip_pkgs = package_info(req_file)
    python_exe = str(get_python_path(env_name))

    # 2. Install Conda-only packages
    if conda_pkgs:
        print(f"Installing Conda-only packages: {conda_pkgs}")
        subprocess.run(
            ["conda", "install", "-n", env_name, *conda_pkgs, "--yes"],
            check=True,
            shell=IS_WIN,
        )

    # 3. Install the rest with UV (Lightning fast)
    use_uv = shutil.which("uv") is not None
    installer = ["uv", "pip"] if use_uv else [python_exe, "-m", "pip"]

    if pip_pkgs:
        print(f"Installing Pip packages via {'uv' if use_uv else 'pip'}...")
        cmd = (
            [*installer, "install", "--python", python_exe]
            if use_uv
            else [*installer, "install"]
        )
        subprocess.run([*cmd, *pip_pkgs], check=True, shell=IS_WIN)

    return env_name


def set_ipykernel(env_name):
    print(f"Setting ipykernel for '{env_name}'...")
    python_exe = str(get_python_path(env_name))
    use_uv = shutil.which("uv") is not None

    # Install ipykernel using uv if available
    install_cmd = (
        ["uv", "pip", "install", "--python", python_exe, "ipykernel"]
        if use_uv
        else [python_exe, "-m", "pip", "install", "ipykernel"]
    )

    subprocess.run(install_cmd, check=True, shell=IS_WIN)

    # Register kernel
    subprocess.run(
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
        check=True,
        shell=IS_WIN,
    )


def test_talktorial(talktorial_dir: Path, env_name: str):
    talktorial = talktorial_dir / TALKTORIAL_FILE
    if talktorial.exists():
        print(f"Testing talktorial {talktorial}")
        python_exe = str(get_python_path(env_name))
        use_uv = shutil.which("uv") is not None

        # Fast install test deps
        install_cmd = (
            ["uv", "pip", "install", "--python", python_exe, "pytest", "nbval"]
            if use_uv
            else [python_exe, "-m", "pip", "install", "pytest", "nbval"]
        )
        subprocess.run(install_cmd, check=True, shell=IS_WIN)

        # Run test using the env's python to ensure context
        subprocess.run(
            [python_exe, "-m", "pytest", "--nbval-lax", str(talktorial)],
            check=True,
            shell=IS_WIN,
        )


def conda_env_list():
    """
    List all conda environments.
    returns:
        list: List of conda environment names.
    """
    result = subprocess.run(
        ["conda", "env", "list"],
        capture_output=True,
        text=True,
        shell=IS_WIN,
    )
    if result.returncode != 0:
        controlled_crash("Error listing conda environments: " + result.stderr)

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
        subprocess.run(notebook_cmd, shell=True)
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


def main():
    parser = argparse.ArgumentParser(description="CLI.")
    parser.add_argument(
        "--talktorial", "-t", help="Taltorial to run, e.g., T001", required=True
    )
    parser.add_argument(
        "--test", action="store_true", help="Test the talktorial using pytest."
    )
    args = parser.parse_args()
    run(args.talktorial, args.test)


if __name__ == "__main__":
    main()
