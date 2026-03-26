import os
import argparse
import requests
from time import sleep

# Configuration defaults
OWNER = "volkamerlab"
REPO = "teachopencadd"
API_ROOT_PATH = "teachopencadd/talktorials/"
DEFAULT_BRANCH = "sepenv"
EXCLUDE_FILES = {"talktorial.ipynb"}
API_BASE = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{API_ROOT_PATH}"
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER}/{REPO}"  # raw base -> /{branch}/{path}
OUTPUT_DIR = f"./"

def github_get(api_url, params=None, timeout=15):
    """Perform an unauthenticated GET to the GitHub API. Raises on non-200."""
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "download-script"}
    try:
        r = requests.get(api_url, headers=headers, params=params, timeout=timeout)
    except requests.RequestException as e:
        raise SystemExit(f"Network error while accessing {api_url}: {e}")
    if r.status_code == 403 and "rate limit" in r.text.lower():
        raise SystemExit(f"GitHub API rate limit reached (HTTP 403). Try again later or use an authenticated token.")
    if r.status_code != 200:
        raise SystemExit(f"GitHub API error {r.status_code} for {api_url}: {r.text}")
    return r.json()


def fetch_folder_contents(api_url, branch, exclude_files=None):
    """
    Recursively fetch a list of (path, raw_download_url) tuples for every file
    under the directory represented by api_url. This function appends ?ref=branch
    for every API request so the branch is respected.
    """
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
            print(f"Skipping unsupported type '{item_type}' at {path}")
    return file_list


def download_file(raw_url, local_path, timeout=30):
    """Download a raw file url and save it to local_path (creating directories as needed)."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        r = requests.get(raw_url, timeout=timeout)
    except requests.RequestException as e:
        print(f"Network error downloading {raw_url}: {e}")
        return False
    if r.status_code == 200:
        with open(local_path, "wb") as fh:
            fh.write(r.content)
        print(f"{local_path}")
        return True
    else:
        print(f"Failed to download {raw_url} (HTTP {r.status_code})")
        return False


def main(talktorial, branch, output_dir):
    api_root_with_path = API_BASE + talktorial 
    os.makedirs(output_dir, exist_ok=True)

    print(f"Fetching file list from branch '{branch}' ...")
    all_files = fetch_folder_contents(api_root_with_path, branch, exclude_files=EXCLUDE_FILES)
    print(f"Found {len(all_files)} files to download (excluded: {EXCLUDE_FILES})\n")

    for path, raw_url in all_files:
        rel_local = os.path.relpath(path, API_ROOT_PATH+talktorial)
        local_path = os.path.join(output_dir, rel_local)
        if os.path.exists(local_path):
            try:
                existing_size = os.path.getsize(local_path)
                if existing_size > 0:
                    print(f"Skipping already existing file: {local_path}")
                    continue
            except OSError:
                pass

        success = download_file(raw_url, local_path)
        if not success:
            print(f"Warning: failed to fetch {raw_url}")

    print(f"\nDone. Files saved under: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download TeachOpenCADD talktorials from a specific branch.")
    parser.add_argument("--talktorial", "-t", help="Taltorial to download, e.g., T001_query_chembl", required=True)
    parser.add_argument("--branch", "-b", default=DEFAULT_BRANCH, help="Git branch to download from (default: sepenv).")
    parser.add_argument("--output_dir", "-o", default=OUTPUT_DIR, help="download location.")
    args = parser.parse_args()

    main(args.talktorial, args.branch, args.output_dir)
