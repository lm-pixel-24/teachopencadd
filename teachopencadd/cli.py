import argparse
import sys
from pathlib import Path

from .config import Settings, settings as default_settings
from .console import print_err, print_status, print_step
from .env import build_jupyter_env_vars, cleanup, configure_env
from .exceptions import TeachOpenCADDError
from .github import fetch_talktorial
from .jupyter import setup_jupyter, test_talktorial
from .models import Talktorial
from .runner import run_command


def _parse_t_id(raw: str) -> str:
    cleaned = raw.lower().lstrip("t").split("_")[0]
    try:
        return f"T{int(cleaned):03d}"
    except ValueError:
        raise TeachOpenCADDError(f"Invalid talktorial ID: '{raw}'")


def _find_or_fetch_talktorial(t_id: str, cfg: Settings) -> Talktorial:
    matches = list(cfg.base_dir.glob(f"{t_id}_*")) if cfg.base_dir.exists() else []
    if not matches:
        print_status(f"Could not find {t_id} locally. Fetching from GitHub...")
        directory = fetch_talktorial(t_id, cfg=cfg)
    else:
        directory = matches[0]
    return Talktorial(t_id=t_id, directory=directory)


def main(cfg: Settings = default_settings) -> int:
    parser = argparse.ArgumentParser(
        description="TeachOpenCADD Talktorial Runner",
        epilog="Visit https://projects.volkamerlab.org/teachopencadd for further information.",
    )
    parser.add_argument("talktorial", nargs="?", help="Talktorial ID (e.g. T001 or 1)")
    parser.add_argument(
        "-c", "--cleanup", action="store_true", help="Remove talktorial environments"
    )
    parser.add_argument(
        "-f", "--force", action="store_true", help="Skip confirmation prompts"
    )
    parser.add_argument(
        "-d", "--download-data", action="store_true", help="Download data only"
    )
    parser.add_argument("-t", "--test", action="store_true", help="Run nbval tests")
    parser.add_argument(
        "-e",
        "--env-dir",
        type=str,
        default=str(cfg.uv_env_root),
        metavar="DIR",
        help="Location for environment storage",
    )
    parser.add_argument(
        "-b",
        "--branch",
        type=str,
        default=cfg.branch,
        metavar="BRANCH",
        help="Github branch for downloads",
    )
    args = parser.parse_args()

    cfg.branch = args.branch
    env_root = Path(args.env_dir)
    print_status(f"Environment directory: {env_root}")

    try:
        if args.cleanup:
            cleanup(args.force, env_root, cfg)
            return 0

        if not args.talktorial:
            print(parser.format_help())
            return 0

        t_id = _parse_t_id(args.talktorial)

        if args.download_data:
            fetch_talktorial(t_id, data_only=True, cfg=cfg)
            return 0

        talk = _find_or_fetch_talktorial(t_id, cfg)
        env = configure_env(t_id, talk.req_file, env_root, cfg)
        env_vars = build_jupyter_env_vars(env)

        setup_jupyter(env, talk.nb_file)

        jupyter_bin = env.bin_dir / ("jupyter.exe" if cfg.is_win else "jupyter")
        if not jupyter_bin.exists():
            raise TeachOpenCADDError(f"Jupyter binary not found at {jupyter_bin}")

        if args.test:
            test_talktorial(talk.nb_file, env, env_vars)
            return 0

        print_step(f"Starting {t_id}...")
        run_command(
            [str(jupyter_bin), "notebook", str(talk.nb_file), "--port", "9999"],
            env=env_vars,
            capture_output=False,
        )

    except TeachOpenCADDError as exc:
        print_err(str(exc))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
