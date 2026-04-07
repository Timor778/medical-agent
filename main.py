from pathlib import Path
import sys

import uvicorn


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
# 这个项目采用 src 布局，直接运行根目录脚本时，
# 需要手动把 src 加进 Python 模块搜索路径里。
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


if __name__ == "__main__":
    # 这里只负责启动 Web 服务。
    # 真正的 Agent 逻辑在 medical_agent.web.app 和 graph/ 目录里。
    uvicorn.run("medical_agent.web.app:app", host="127.0.0.1", port=8000, reload=True)
