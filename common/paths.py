"""
common/paths.py - 統一的路徑解析

舊專案（BilateralCoordinationTraining、press_pin）踩過三次同樣的坑：用 cwd
相對路徑 (例如 "assets/font/xxx.ttc"、".\\model") 存取檔案，只要執行時的工作
目錄不是專案資料夾，就會 FileNotFoundError / ValueError。

這支檔案是整個新專案「唯一」允許用來組出絕對路徑的地方：所有模組（model
載入、data/users 資料夾、字型、圖片…）都要透過 resource_path()，不能自己寫死
相對路徑，也不能依賴 os.getcwd()。

注意：這支檔案本身放在 common/ 底下，所以 __file__ 是 common/paths.py，要往上
一層才是專案根目錄（S:\\CODES\\WORK\\GAME\\NEW\\）。
"""

import os
import sys

# common/paths.py -> 上一層就是專案根目錄
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(rel_path: str) -> str:
    """把相對路徑換成絕對路徑，基準是「專案根目錄」，不受執行時 cwd 影響。

    打包成 PyInstaller exe 之後，資源會被解壓到 sys._MEIPASS 指向的暫存資料夾，
    所以這裡也比照舊專案的作法保留這個分支。
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = PROJECT_ROOT
    return os.path.join(base, rel_path)


def ensure_dir(path: str) -> str:
    """確保資料夾存在（給 data/users 這類需要先建立目錄的地方用），回傳同一個路徑方便串接。"""
    os.makedirs(path, exist_ok=True)
    return path
