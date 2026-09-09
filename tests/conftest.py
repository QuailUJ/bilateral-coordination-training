import os
import sys

# 讓 pytest 不管從哪個目錄執行，都能 import 到專案根目錄下的 common / data_store / games 等套件。
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
