# 開發與手動安裝

[回首頁](../README.md) · [安裝懶人包](QUICKSTART.md) · [遊戲介紹](GAME_GUIDE.md) · [更新紀錄](../CHANGELOG.md)

一般使用者請先依 [安裝懶人包](QUICKSTART.md) 操作。以下提供手動安裝、測試與程式結構。

## 下載程式

儲存庫：<https://github.com/QuailUJ/bilateral-coordination-training>

這是私人儲存庫，需要登入有存取權限的 GitHub 帳號。其他使用者須先由擁有者加入協作者。

### 方法 A：下載 ZIP（不需要 Git）

1. 開啟上面的 GitHub 頁面。
2. 點 **Code → Download ZIP**。
3. 將 ZIP **完整解壓縮**，例如放在 `C:\Games\bilateral-coordination-training-main`。
4. 開啟解壓後的資料夾，確認裡面有 `main.py`、`requirements.txt`、`assets` 和 `model`。
5. 雙擊 `install.bat` 安裝，再雙擊 `start_game.bat` 啟動。若偏好手動安裝，再按照下方指令操作。

### 方法 B：使用 Git

先安裝 [Git for Windows](https://git-scm.com/download/win)，重新開啟 PowerShell 後執行：

```powershell
git clone https://github.com/QuailUJ/bilateral-coordination-training.git
cd bilateral-coordination-training
```

若出現 GitHub 登入視窗，登入有此儲存庫權限的帳號。不要將密碼或存取權杖寫進程式、README 或遠端網址。

## 安裝 Python

1. 到 [Python 3.11.9 官方下載頁](https://www.python.org/downloads/release/python-3119/) 選擇 **Windows installer (64-bit)** 安裝。
2. 安裝時勾選 **Add python.exe to PATH**，並保留 Python Launcher。
3. 安裝完成後重新開啟 PowerShell，確認版本：

```powershell
py -3.11 --version
```

應顯示 `Python 3.11.x`。本專案建議先用 3.11，避免較新 Python 版本與影像套件不相容。

## 建立環境並安裝套件

以下指令都在**有 `main.py` 的專案根目錄**執行：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

第一次安裝需要網路，可能需要幾分鐘。`.venv` 是這台電腦專用的環境，不會上傳至 GitHub；換電腦時重新執行上述步驟即可。

這裡直接呼叫虛擬環境的 Python，**不需要啟用 `Activate.ps1`，也不需要更改 PowerShell 執行原則**。

若 `py` 找不到，但 `python --version` 已確定是 Python 3.11，可以改用：

```powershell
python -m venv .venv
```

其餘安裝指令維持不變。

## 啟動遊戲

先接上攝影機，再執行：

```powershell
.\.venv\Scripts\python.exe main.py
```

程式會開啟全螢幕視窗。輸入使用者名稱後，按「登入／建立新使用者」即可進入。這是本機使用者名稱管理，沒有密碼驗證。

### 資源檔案

下載內容已包含：

- `model/hand_landmarker.task`：MediaPipe 手部模型。
- `model/pose_landmarker_full.task`：MediaPipe 身體姿勢模型，供手肘角度偵測使用。
- `assets/font/msjh.ttc`：中文顯示字型。
- `assets/image/`：遊戲圖片。
- `assets/sound/`：遊戲音效。

請保留資料夾結構。使用上述 Python 指令啟動，不需要另外下載模型或手動複製舊專案。

## 開發與測試

安裝測試依賴並執行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

測試使用合成座標及暫存使用者資料，不需要真人入鏡。自動測試涵蓋動作判定、計分、回放、使用者管理及背景存檔；真人操作時的光線、遮擋及攝影機差異仍需實際確認。

`main.spec` 是供開發者參考的 PyInstaller 設定；目前標準安裝方式是本 README 的 Python 原始碼執行流程，未提供已驗證的安裝程式。

## 專案結構

```text
main.py                 # 啟動入口
common/                 # 攝影機、手部身分追蹤、背景儲存及共用狀態
data_store/             # 使用者與設定存取
games/                  # 四款遊戲的畫面、動作與計分
scenes/                 # 登入、選單、設定、歷史與回放
ui/                     # 共用介面元件
assets/                 # 字型、圖片、音效
model/                  # MediaPipe 模型
tests/                  # 自動測試
requirements.txt        # 執行套件
requirements-dev.txt    # 開發／測試套件
```

字型、模型、圖片與音效保留各自原有授權；本儲存庫未另外授予這些素材的再散布授權。
