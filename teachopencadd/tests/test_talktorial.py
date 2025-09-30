import subprocess
import pytest

# List the talktorial IDs you want to test
talktorial_ids = ["T001"]  # add more IDs as needed

@pytest.mark.parametrize("tid", talktorial_ids)
def test_talktorial_runs(tid):
    """
    Run `main.py <tid>` and assert it completes without errors.
    """
    result = subprocess.run(
        ["python", "main.py", tid],
        capture_output=True,
        text=True
    )

    # Print stdout/stderr for debug if the test fails
    print("STDOUT:\n", result.stdout)
    print("STDERR:\n", result.stderr)

    # Assert the script exited successfully
    assert result.returncode == 0, f"{tid} failed"
