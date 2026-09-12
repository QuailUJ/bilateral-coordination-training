# 下載與安裝懶人包

[回首頁](../README.md) · [安裝懶人包](QUICKSTART.md) · [遊戲介紹](GAME_GUIDE.md) · [更新紀錄](../CHANGELOG.md)

## 下載與安裝

**Windows 10／11（64 位元）＋攝影機；第一次安裝需要網路。不用自己輸入指令，也不用先手動安裝 Python。**

1. 點 [最新版 ZIP 下載](https://github.com/QuailUJ/bilateral-coordination-training/archive/refs/heads/main.zip)，或到 [專案首頁](https://github.com/QuailUJ/bilateral-coordination-training) 點 **Code → Download ZIP**，下載後按右鍵「全部解壓縮」。
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

## 安裝完接著做什麼

用同一資料夾的 `start_game.bat` 啟動，它會明確呼叫 `.venv\Scripts\python.exe`；不需要先啟用虛擬環境。遊戲玩法請看 [遊戲介紹與操作](GAME_GUIDE.md)，手肘工具請看 [手肘工具懶人包](ELBOW_GUIDE.md)。

## 個人資料放在哪裡？

以原始碼啟動時，程式會自動建立：

```text
data/
├── users/          # 使用者、成績、逐幀回放 JSON
└── settings.json   # 攝影機選擇、音量等本機設定
```

`data/` 已列入 `.gitignore`，不會跟著程式上傳。此儲存庫不包含開發機的 666 帳號或其他測試紀錄。

備份或換電腦時，先正常關閉遊戲，再自行複製整個 `data` 資料夾到新電腦的專案根目錄。長時間訓練的逐幀紀錄可能較大。

## 更新程式

先正常關閉遊戲，建議先備份 `data/`。

使用 Git 下載者：

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

如果自己修改過程式而無法更新，先保存自己的修改，再處理衝突；不要直接強制覆寫。

使用 ZIP 下載者：重新下載並解壓到新資料夾，重新建立環境，然後將原本的 `data/` 複製過去。

## 常見問題

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

## 安裝成功但遊戲很卡

安裝檔檢查 Python 與套件可否載入，不會自動判斷電腦效能。請記錄是整個畫面卡，還是畫面順但手勢反應慢，並提供電腦規格、遊戲版本與攝影機資訊。不同電腦的效能不能由安裝成功保證。

需要手動安裝或查看原始碼結構，請看 [開發與手動安裝](DEVELOPMENT.md)。
