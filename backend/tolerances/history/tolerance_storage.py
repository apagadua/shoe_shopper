import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent

TOL_FILE = BASE_DIR / "tolerances.json"
HISTORY_DIR = BASE_DIR / "history"


def load_tolerances():
    with open(TOL_FILE, "r") as f:
        return json.load(f)


def save_tolerances(tolerances):
    # overwrite current
    with open(TOL_FILE, "w") as f:
        json.dump(tolerances, f, indent=2)

    # history snapshot
    HISTORY_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    history_file = HISTORY_DIR / f"tolerances_{timestamp}.json"

    with open(history_file, "w") as f:
        json.dump(tolerances, f, indent=2)