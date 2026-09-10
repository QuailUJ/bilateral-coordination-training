# 雙側協調訓練遊戲

使用 **Python、Pygame、OpenCV 與 MediaPipe** 的攝影機互動訓練平台，提供拳頭、手指、光劍及按壓遊戲，以及使用者管理、成績紀錄和回放。

目前以 **Windows 10／11、64 位元 Python 3.11** 為主要執行環境。開發機使用 Python 3.11.9；其他作業系統尚未完成實機驗證。

## 第一次使用：下載 → 安裝 → 開始玩

**不用自己輸入指令，也不用先手動安裝 Python。**

1. 在本頁上方點綠色 **Code → Download ZIP**，下載後按右鍵「全部解壓縮」。
2. 打開解壓後的資料夾，雙擊 **`install.bat`**，等到出現綠色 **Installation complete!**。
3. 接上攝影機，雙擊 **`start_game.bat`**，就能開始玩。

| 檔案 | 什麼時候使用 |
| --- | --- |
| **`install.bat`** | 第一次使用、換電腦或更新套件時，雙擊安裝環境 |
| **`start_game.bat`** | 之後每次玩遊戲，雙擊啟動 |
| **`start_elbow.bat`** | 雙擊啟動手肘 3D 角度偵測；尚未建立環境時會自動安裝 |
| `requirements.txt` | 套件清單，由安裝檔自動讀取，不需要自己打開執行 |

安裝需要網路。安裝檔會檢查 64 位元 Python 3.11；若沒有，會從 Python 官網下載並驗證安裝程式，安裝 Python 3.11.9，接著建立 `.venv` 並安裝所有必要套件。已經有可用環境時會重複利用，可再次執行。

請先**完整解壓縮**，不要在 ZIP 裡直接執行，也不要只下載這兩個 `.bat`。若安裝失敗，視窗會留下錯誤訊息；處理問題後再雙擊 `install.bat`。若既有 `.venv` 不相容，先將它重新命名，再重新安裝。

此儲存庫是私人的，下載前須登入有權限的 GitHub 帳號。遊戲模型、圖片、字型與音效都已包含；使用者資料會保存在本機 `data/`。

### 手肘角度偵測懶人包

1. 下載整份 ZIP 並「全部解壓縮」。
2. 接上攝影機，關閉其他占用攝影機的程式。
3. 雙擊 **`start_elbow.bat`**。第一次會自動安裝 Python、建立 `.venv`、安裝套件，再開啟偵測視窗；之後直接啟動。

遊戲與手肘程式共用同一個 `.venv`，模型已隨專案附上，不需另外下載。首次安裝需要網路；若套件缺漏或環境需要更新，雙擊 `install.bat` 修復。

視窗預設 960 × 720，可拖曳調整大小；按 **Q** 或 **Esc** 離開。使用攝影機 0，顯示上臂與前臂的 3D 屈曲角度（伸直為 0°）。角度是一般攝影機影像的模型估計，目前仍有準確度限制。

以下是手動安裝與詳細操作說明；**一鍵安裝成功後，可直接跳到「5. 操作與遊戲內容」**。

## 1. 下載程式

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

## 2. 安裝 Python

1. 到 [Python 3.11.9 官方下載頁](https://www.python.org/downloads/release/python-3119/) 選擇 **Windows installer (64-bit)** 安裝。
2. 安裝時勾選 **Add python.exe to PATH**，並保留 Python Launcher。
3. 安裝完成後重新開啟 PowerShell，確認版本：

```powershell
py -3.11 --version
```

應顯示 `Python 3.11.x`。本專案建議先用 3.11，避免較新 Python 版本與影像套件不相容。

## 3. 建立環境並安裝套件

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

## 4. 啟動遊戲

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

## 5. 操作與遊戲內容

| 畫面名稱 | 內容 | 程式資料夾 |
| --- | --- | --- |
| 遊戲零 | 左右拳心移動；每手可選不使用、垂直、水平、順時針、逆時針 | `games/game1_bilateral_vertical` |
| 遊戲一 | 食指伸展與左右手動作組合 | `games/game2_finger_vertical` |
| 遊戲二 | 光劍擊球 | `games/game3_lightsaber_marble` |
| 遊戲三 | 雙手按壓與三角形判定 | `games/game4_bilateral_press` |

資料夾編號保留開發時命名，因此比畫面顯示的遊戲編號多一。

### 遊戲零：拳頭動作

- 左右手各自選一項；選「不使用」的手不需要出現在鏡頭中。
- 水平／垂直以反向移動確認極限點，兩個相反方向的有效段算一組，不必回到固定基準。
- 畫圓從預計的 **12 點鐘位置**開始：順時針為畫面上的上→右→下→左→上，逆時針反向。
- 回到上方後，**再稍微向下**確認上方反轉點，結算當圈並開始下一圈。不要求接回原本座標，也不使用預設圓心。
- 畫圓軌跡按每隻手的圈別保留；短暫漏偵測會斷線，較長缺失或身分不確定時會重置未完成動作。
- 正式遊戲目標為十組。單手畫圓以平均圓度評分；雙圓組合包含開始時間、耗時與圓度配對評分；混合軸向／畫圓保留同步視窗計分。

### 登入頁的「測試版右手畫圓」

先輸入使用者名稱，再按此按鈕。只使用右手順時針，**五圈結束**，使用與正式遊戲零共用的上方反轉判定。第五圈也要在回到上方後稍微往下，才能確認完成。結果頁可立即回放。

### 設定、成績及回放

- 點「設定」或按 **F1** 可調整音量、選擇攝影機；登入頁按 Esc 也可開啟設定。
- 其他畫面按 **Esc** 通常會返回上一頁。退出程式可使用登入頁右上角的按鈕。
- 主畫面的設定可管理、刪除使用者及其資料。
- 「歷史成績」可選擇紀錄進行回放或刪除。
- 回放支援暫停、慢速／加速、拖曳時間軸與事件定位；較舊紀錄可能沒有完整逐幀資訊。
- 回放保存的是軌跡、遊戲狀態與判定資料，**不是攝影機原始影片**。光劍／三角形回放會列出得分、扣分或未得分事件。

### 結算期間

動作完成後停止本次計次，攝影機畫面仍會更新。資料在背景儲存，完成後顯示結果。若存檔失敗，畫面會顯示原因，可按 **R** 重試；程式關閉時會等待已提交的存檔工作完成。

## 6. 個人資料放在哪裡？

以原始碼啟動時，程式會自動建立：

```text
data/
├── users/          # 使用者、成績、逐幀回放 JSON
└── settings.json   # 攝影機選擇、音量等本機設定
```

`data/` 已列入 `.gitignore`，不會跟著程式上傳。此儲存庫不包含開發機的 666 帳號或其他測試紀錄。

備份或換電腦時，先正常關閉遊戲，再自行複製整個 `data` 資料夾到新電腦的專案根目錄。長時間訓練的逐幀紀錄可能較大。

## 7. 更新程式

先正常關閉遊戲，建議先備份 `data/`。

使用 Git 下載者：

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

如果自己修改過程式而無法更新，先保存自己的修改，再處理衝突；不要直接強制覆寫。

使用 ZIP 下載者：重新下載並解壓到新資料夾，重新建立環境，然後將原本的 `data/` 複製過去。

## 8. 常見問題

### 找不到 `py`、`python` 或套件

重新開啟終端機，確認已安裝 Python 3.11。啟動時請使用 `.\.venv\Scripts\python.exe`，不要混用另一套 Python。

### 攝影機沒有畫面

1. 確認 USB 攝影機已連接，並關閉其他可能占用鏡頭的程式。
2. 在 Windows 設定中允許桌面應用程式使用攝影機。
3. 開啟遊戲設定，切換攝影機編號並確認預覽。

沒有成功開啟攝影機時仍可進入設定頁修正，不需要修改原始碼。

### 模型或中文字型找不到

確認 ZIP 已完整解壓縮，並檢查 `model/hand_landmarker.task` 和 `assets/font/msjh.ttc` 是否存在。不要只下載 `main.py`。

### 顯示 GPU 初始化失敗

程式會自動嘗試改用 CPU。只要後續成功啟動並有畫面，通常可以繼續使用；不要求另外安裝 CUDA。

### 有畫圓但尚未計次

先確認所選方向與畫面一致。回到上方後稍微往下，讓系統確認上方極限點；同時看左右側提示，分辨是缺失、幅度不足還是未形成完整繞行。可在回放檢查當時狀態。

## 9. 開發與測試

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
