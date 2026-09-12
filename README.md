# 雙側協調訓練遊戲

> **MID 中版**：以 `37674c0` 為基準，只調整遊戲零的快速移動與短暫斷訊恢復。請先看 [本次調整與測試說明](TRACKING_NOTES.md)。下方為基準版本原有操作說明。

**[下載 MID 懶人包](https://github.com/QuailUJ/bilateral-coordination-training/archive/refs/heads/MID.zip)** · [MID 更新紀錄](CHANGELOG.md) · [三版比較](https://github.com/QuailUJ/bilateral-coordination-training#readme)

請登入有私人儲存庫權限的帳號，下載並完整解壓到獨立的 MID 資料夾，第一次雙擊 `install.bat`，安裝完再雙擊 `start_game.bat`。不要和 OLD、NEW 同時開啟攝影機。

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

請先**完整解壓縮**，不要在 ZIP 裡直接執行，也不要只下載 `.bat` 檔。若安裝失敗，視窗會留下錯誤訊息；處理問題後再雙擊 `install.bat`。若既有 `.venv` 不相容，先將它重新命名，再重新安裝。

此儲存庫是私人的，下載前須登入有權限的 GitHub 帳號。遊戲模型、圖片、字型與音效都已包含；使用者資料會保存在本機 `data/`。

### 手肘角度偵測懶人包

#### A. 使用前準備

- Windows 10／11（64 位元）電腦，以及可用的內建或 USB 攝影機。
- 首次安裝需要網路；安裝完成後，攝影機辨識可在本機離線執行。
- 不需預先安裝 Python、Git 或程式編輯器，也不用輸入指令。
- 若 GitHub 頁面顯示 404，請確認登入的帳號具有此私人儲存庫的存取權限。

#### B. 下載與完整解壓縮

1. 開啟 [GitHub 專案頁面](https://github.com/QuailUJ/bilateral-coordination-training)。
2. 點綠色 **Code → Download ZIP**。
3. 下載完成後，在 ZIP 上按右鍵，選擇 **全部解壓縮**，例如解壓到 `C:\Games\bilateral-coordination-training-main`。
4. 開啟解壓後的資料夾，找到 `start_elbow.bat`。請保留整份資料夾，不要單獨搬走啟動檔。

完整下載中應包含以下項目；`.venv` 由安裝程式產生，ZIP 裡沒有是正常的：

| 項目 | 用途 |
| --- | --- |
| `start_elbow.bat` | 手肘偵測的一鍵安裝／啟動入口 |
| `install.bat`、`scripts/install.ps1` | 環境安裝與修復 |
| `elbow_angle_tracker.py` | 手肘偵測程式 |
| `requirements.txt` | 自動安裝使用的套件清單 |
| `model/pose_landmarker_full.task` | 手肘使用的身體姿勢模型 |
| `model/hand_landmarker.task` | 原遊戲使用的手部模型 |
| `main.py`、`common/`、`games/`、`scenes/`、其他資料夾 | 共用程式與遊戲資源，請一併保留 |

#### C. 第一次雙擊啟動

1. 接上攝影機，關閉正在使用攝影機的相機 App、視訊會議或其他偵測程式。
2. 雙擊 **`start_elbow.bat`**。
3. 若尚未建立 `.venv`，會開啟命令視窗，自動執行安裝。請保持網路連線，等待以下流程完成：
   - 檢查可用的 **64 位元 Python 3.11**；沒有時，從 Python 官網下載並驗證安裝程式，安裝 Python 3.11.9。
   - 在專案資料夾建立 **`.venv`**。
   - 依 `requirements.txt` 安裝 Pygame、OpenCV、MediaPipe 等套件。
   - 檢查套件相容性、程式匯入與兩個模型檔案是否存在。
4. 出現 **`Installation complete!`** 後，啟動腳本會接著開啟 **Elbow Angle Tracker**，不需要再輸入指令。

如果已經安裝過同資料夾的遊戲環境，會直接共用 `.venv`，不會每次重新下載套件。若環境已存在但套件不完整，請先雙擊 **`install.bat`** 修復，再啟動。

也可以分兩步操作：先雙擊 `install.bat`，等安裝完成後按任意鍵關閉安裝視窗，再雙擊 `start_elbow.bat`。

#### D. 畫面操作與數字說明

- 視窗預設 **960 × 720**，可拖曳邊框調整大小或最大化。
- 讓要量測的肩膀、手肘與手腕完整入鏡，避免被畫面邊緣裁掉或互相遮擋。
- `L Elbow`／`R Elbow` 表示模型判定的人物左／右手肘。
- 角度使用模型的 **3D 世界座標**計算上臂與前臂的屈曲程度：**伸直為 0°，彎成直角為 90°**。
- `FPS` 是實際處理更新速度；`Camera read` 是攝影機讀取耗時，`Pose` 是姿勢辨識耗時，單位皆為毫秒。視窗變大不代表攝影機或辨識會達到 60 FPS。
- 點選偵測視窗，使其取得鍵盤焦點，再按 **Q** 或 **Esc** 正常離開。

**目前角度仍有準確度限制。** 3D 座標來自一般攝影機影像的模型估計，並非深度感測器實測；即使畫面看起來接近直角，顯示值仍可能有明顯誤差。安裝成功代表程式可執行，不代表角度準確度已驗證。

手肘程式目前固定使用 **攝影機 0**，沒有攝影機選擇介面，也不會跟隨原遊戲的攝影機設定。若有多顆攝影機且開錯裝置，需要協助調整 `elbow_angle_tracker.py` 的 `camera_index`。

#### E. 之後使用、更新與換電腦

- **日常啟動：** 雙擊 `start_elbow.bat` 即可；玩原遊戲則雙擊 `start_game.bat`。
- **更新套件或修復缺少套件：** 關閉程式，雙擊 `install.bat`，成功後重新啟動。
- **用 ZIP 更新程式：** 關閉舊程式，下載最新版 ZIP，解壓到新資料夾，再雙擊新資料夾的 `start_elbow.bat` 建立環境。確認新版可用前保留舊資料夾；若需要原遊戲的帳號與紀錄，可在兩邊程式都關閉時，將舊資料夾的 `data/` 複製到新資料夾。
- **換電腦或分享給別人：** 傳送 GitHub 專案連結或完整程式 ZIP，讓對方重新安裝。不要複製 `.venv`，也不要把自己的 `data/` 帳號與紀錄一起分享。

#### F. 常見問題

| 狀況 | 處理方式 |
| --- | --- |
| 安裝下載失敗、網路逾時 | 確認網路可連線，保留錯誤訊息，再雙擊 `install.bat` 重試 |
| `Existing .venv is invalid or incompatible` | 關閉程式，把專案內的 `.venv` 重新命名成尚不存在的備份名稱，例如 `.venv-backup`，再雙擊 `install.bat` |
| `ModuleNotFoundError` 或套件匯入失敗 | 雙擊 `install.bat` 修復；若仍失敗，提供命令視窗的完整錯誤訊息 |
| `Missing model` 或找不到 `.task` | 重新下載整份 ZIP 並完整解壓縮，確認 `model/` 中兩個模型都存在 |
| `攝影機 0 開啟失敗` | 確認攝影機接妥、關閉其他占用程式，並確認 Windows 允許桌面應用程式使用攝影機；多顆攝影機時可能需要調整索引 |
| 出現 GPU 初始化失敗，但接著顯示使用 CPU | 程式有 CPU 備援，可繼續執行；若程式退出，請查看最後的錯誤訊息 |
| 畫面有影像但沒有骨架或角度 | 調整站位與光線，讓肩、肘、腕都入鏡；關節未通過可見度檢查時不會顯示該側手臂 |
| 視窗顯示 `Tracker stopped with an error` | 截取命令視窗中的完整錯誤，尤其最後幾行，提供給維護者排查 |

安裝腳本會在錯誤時停下，手肘啟動腳本會保留錯誤視窗；請先記下訊息，再按任意鍵關閉。

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
