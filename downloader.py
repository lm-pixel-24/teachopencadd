import os
import sys
import requests


def download_requirements(requirements_url, 
                            requirements_target = 'requirements.txt'):
    """
    Downloads the requirements.txt file from the specified URL.
    """
    
    try:
        # Check if the requirements file already exists
        if os.path.exists(requirements_target):
            print(f"{requirements_target} file already exists.")
            sys.exit(1)
        else:
            print(f"Downloading {requirements_target}...")
            response = requests.get(requirements_url)
            response.raise_for_status()
            with open(requirements_target, 'wb') as f:
                f.write(response.content)

    except Exception as e:
        print(f"Error checking {requirements_target}: {e}")
        sys.exit(1)
    

def download_contents(content_url, target_folder):
    """
    Downloads the required content from the GitHub repository.
    """
    try:
        print(f"Downloading {target_folder}...")

        # Create local target folder
        os.makedirs(target_folder, exist_ok=False)

        # Get list of files in the GitHub folder
        response = requests.get(content_url)
        response.raise_for_status()
        files = response.json()

        # Download each file
        for file_info in files:
            download_url = file_info['download_url']
            file_name = file_info['name']
            file_path = os.path.join(target_folder, file_name)

            print(f"Downloading {file_name}...")
            file_response = requests.get(download_url)
            file_response.raise_for_status()

            with open(file_path, 'wb') as f:
                f.write(file_response.content)

    except requests.RequestException as e:
        print(f"Error downloading content: {e}")
        sys.exit(1)


def main():
    """
    Main function to run the downloader script.
    """
    # Handle requirements.txt separately as it's a raw file
    if len(sys.argv) == 2:
        requirements_url = sys.argv[1]
        requirements_target = 'requirements.txt'
        download_requirements(requirements_url)

    elif len(sys.argv) == 3:
        content_url = sys.argv[1]
        concent_folder = sys.argv[2]
        download_contents(content_url, concent_folder)
    
    else:
        print("Something went wrong. Please provide the correct arguments.")
        sys.exit(1)

    print("Download completed successfully.")


if __name__ == "__main__":
    main()