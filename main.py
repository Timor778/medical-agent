from pathlib import Path
import sys

import uvicorn


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


if __name__ == "__main__":
    uvicorn.run("medical_agent.web.app:app", host="127.0.0.1", port=8000, reload=True)
