import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent

ALLURE_RESULTS = BASE_DIR / "reports" / "allure" / "results"
ALLURE_REPORT = BASE_DIR / "reports" / "allure" / "report"

HISTORY_SRC = ALLURE_REPORT / "history"
HISTORY_DST = ALLURE_RESULTS / "history"

def pytest_sessionstart(session):
    ALLURE_RESULTS.mkdir(parents=True, exist_ok=True)
    ALLURE_REPORT.mkdir(parents=True, exist_ok=True)

    if HISTORY_SRC.exists():
        if HISTORY_DST.exists():
            shutil.rmtree(HISTORY_DST)
        shutil.copytree(HISTORY_SRC, HISTORY_DST)


def pytest_sessionfinish(session, exitstatus):
    subprocess.run(
        [
            r"C:/Tools/allure/bin/allure.bat",
            "generate",
            str(ALLURE_RESULTS),
            "-o",
            str(ALLURE_REPORT),
            "--clean",
        ],
        check=False,
    )

    cov_file = BASE_DIR.parent / ".coverage"
    if cov_file.exists():
        cov_file.unlink()