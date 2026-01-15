import os
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
USE_SHELL = 'win' in str(sys.platform.lower())


def package_info(req_file):
    """
    Finds python version and required pckages.

    Args:
        req_file (str): requirements.txt file path.

    Return:
        str : python version. e.g. '3.12.0'
        list : list of required packages. e.g. ['pandas', 'numpy',].
    """
    with open(req_file, "r") as f:
        pkg_info = f.read().strip()
    py_vrs = pkg_info.split("\n")[0]
    assert py_vrs.split("=")[0] == "#python", (
        "First package in requirements file must be "
        "python with specified version. e.g. python=3.12.0"
    )
    py_vrs = re.findall(r"[\d.]+", py_vrs)[0]
    pkgs_lst = pkg_info.split("\n")[1:]
    return py_vrs, pkgs_lst


def conda_env_list():
    """
    List all conda environments.
    returns:
        list: List of conda environment names.
    """
    result = subprocess.run(["conda", "env", "list"], 
                        capture_output=True, 
                        text=True, shell=USE_SHELL)
    if result.returncode != 0:
        controlled_crash("Error listing conda environments: " + result.stderr)

    envs = result.stdout.splitlines()
    return [line.split()[0] for line in envs if line and not line.startswith("#")]


def configure_env(prefix, python_version, req_file):
    """
    Configure a conda environment with the specified
    python version and requirements.

    Args:
        prefix (str): The prefix for the environment, e.g. 'T001'.
        python_version (str): The python version to use, e.g. '3.12.0'.
        req_file (str): requirements.txt file path.
    """
    # env convention:TXXX_py* e.g. T001_312
    env_name = prefix + "_" + python_version.replace(".", "")
    existing_envs = conda_env_list()
    if not env_name in existing_envs:
        print(
            f"Creating conda environment '{env_name}'\
                 with Python {python_version}"
        )
        result = subprocess.run(
            ["conda", "create", "-n", env_name, f"python={python_version}", "--yes"],
            check=True,
            capture_output=True,
            text=True,
            shell=USE_SHELL,
        )
        if result.returncode != 0:
            controlled_crash("Error listing conda environments: " + result.stderr)

    print(f"Installing dependencies in '{env_name}'...")
    # pkg_install_cmd = 'conda run -n '+ env_name + ' pip install '
    # pkg_install_cmd += ' '.join(pkg_list)
    req_file_install_cmd = "conda run -n " + env_name + " pip install -r " + req_file
    print(f"Running command: {req_file_install_cmd}")
    result = subprocess.run(
        req_file_install_cmd, shell=True, capture_output=True, text=True
    )
    if result.returncode != 0:
        controlled_crash("Error installing dependencies: " + result.stderr)
    return env_name


def set_ipykernel(env_name):
    """
    Set the ipykernel for the conda environment.
    """
    print(f"Setting ipykernel for '{env_name}'...")
    # install ipykernel
    result = subprocess.run(
        f"conda run -n {env_name} pip install ipykernel",
        shell=USE_SHELL,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        controlled_crash("Error installing ipykernel: " + result.stderr)
    # set ipykernel
    result = subprocess.run(
        f"conda run -n {env_name} python -m ipykernel install --user \
            --name {env_name} --display-name '{env_name}'",
        shell=USE_SHELL,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        controlled_crash("Error setting ipykernel: " + result.stderr)
    print(f"ipykernel for '{env_name}' set successfully.")


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
        subprocess.run(notebook_cmd, shell=USE_SHELL)
    else:
        controlled_crash(f"Error: Notebook '{talktorial}' not found.")


def test_talktorial(talktorial_dir: Path, env_name: str):
    """Test the Jupyter Notebook inside the correct conda environment."""
    talktorial = talktorial_dir / TALKTORIAL_FILE
    if talktorial.exists():
        print(f"Testing talktorial {talktorial}")
        result = subprocess.run(
            f"conda run -n {env_name} pip install pytest nbval",
            shell=USE_SHELL,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            controlled_crash("Error installing pytest nbval: " + result.stderr)

        notebook_cmd = f"conda run --no-capture-output -n {env_name} pytest --nbval-lax {str(talktorial)}"
        result = subprocess.run(notebook_cmd, shell=USE_SHELL)
        result.check_returncode()
    else:
        controlled_crash(f"Error: Notebook '{talktorial}' not found.")


def controlled_crash(reason, code=1):
    """Print an error message and exit."""
    print("Error: " + reason, file=sys.stderr)
    sys.exit(code)


def main(txxx, test_mode=False):
    talktorial_dir = find_talktorial_folder(txxx)
    print(f"Found talktorial folder: \n{talktorial_dir}")
    req_path = talktorial_dir / REQ_FILE
    req_path = str(req_path)  # convert posixpath to str
    if not os.path.exists(req_path):
        controlled_crash(
            f"Requirements file '{REQ_FILE}' \
                            not found in {talktorial_dir}."
        )
    python_version, pkg_list = package_info(req_path)
    print(f"Python version: {python_version}")
    print(f"Package list: \n{pkg_list}")

    env_name = configure_env(txxx, python_version, req_path)
    print(f"Configured environment: {env_name}")
    set_ipykernel(env_name)
    set_nb_kernelspec(talktorial_dir, env_name)

    if test_mode:
        test_talktorial(talktorial_dir, env_name)
    else:
        start_talktorial(talktorial_dir, env_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI.")
    parser.add_argument(
        "--talktorial", "-t", help="Taltorial to run, e.g., T001", required=True
    )
    parser.add_argument(
        "--test", action="store_true", help="Test the talktorial using pytest."
    )
    args = parser.parse_args()
    main(args.talktorial, args.test)
