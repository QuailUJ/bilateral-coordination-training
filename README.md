# 雙側協調訓練遊戲

## 選擇版本與下載懶人包

| 版本 | 用途與差異 | 下載 |
| --- | --- | --- |
| **OLD 舊版** | `37674c0` 原程式，保留作為比較與測試後路 | [下載 OLD](https://github.com/QuailUJ/bilateral-coordination-training/archive/refs/heads/OLD.zip) |
| **MID 中版** | 從 OLD 小幅優化遊戲零快速移動與短暫斷訊恢復；保留舊動畫與計分 | [下載 MID](https://github.com/QuailUJ/bilateral-coordination-training/archive/refs/heads/MID.zip) |
| **NEW 最新開發版** | 包含後續規則與效能修改；老師電腦曾回報卡頓，保留供比較 | [下載 NEW](https://github.com/QuailUJ/bilateral-coordination-training/archive/refs/heads/NEW.zip) |

**[完整安裝懶人包](docs/QUICKSTART.md)**。三個版本使用 Git 分支管理，不需要懂 Git：點對應 ZIP、分開解壓即可。下方遊戲介紹與詳細文件以 NEW 為準；OLD、MID 的規則請看各自資料夾內的 README。

Windows 10／11（64 位元）＋攝影機。請先登入有此私人儲存庫權限的 GitHub 帳號；第一次安裝需要網路。

1. 下載 ZIP，按右鍵選 **全部解壓縮**。
2. 雙擊 **`install.bat`**，等出現 **Installation complete!**。
3. 接上攝影機，雙擊 **`start_game.bat`** 開始玩。

安裝檔會檢查 Python 並安裝必要套件，不必自己操作 `requirements.txt`。不要在 ZIP 裡直接執行；更新與保留成績的方法請看安裝懶人包。

## 專案介紹

透過攝影機偵測雙手，進行拳頭移動、食指動作、光劍擊球及三角形按壓訓練。支援使用者管理、成績保存與歷史回放，另附手肘角度偵測工具。

## 文件分類

| 想了解什麼 | 請看這裡 |
| --- | --- |
| 下載、安裝、啟動、更新、備份與常見問題 | [安裝懶人包](docs/QUICKSTART.md) |
| 四款遊戲玩法、計分、設定與回放 | [遊戲介紹與操作](docs/GAME_GUIDE.md) |
| 每個版本改了什麼 | [更新紀錄](CHANGELOG.md) |
| 手肘偵測工具的安裝與使用 | [手肘工具懶人包](docs/ELBOW_GUIDE.md) |
| 手動安裝、測試指令與程式結構 | [開發說明](docs/DEVELOPMENT.md) |

## 最近的遊戲更新

2026-09-12：遊戲三還原舊版動畫、音效與計分，只增加「四根手指都要彎下」的判定。其他遊戲保留目前修改。[查看完整更新紀錄](CHANGELOG.md)

## 三個版本如何保留

- 分別解壓至 `OLD`、`MID`、`NEW` 資料夾，每份第一次都執行自己的 `install.bat`，再用同資料夾的 `start_game.bat` 啟動。
- `main` 作為專案首頁，本次與 `NEW` 內容相同。GitHub 分支選單可切換 `OLD`、`MID`、`NEW`。
- 本次發布沒有重新修改任何遊戲規則；MID 的追蹤調整尚需真人測試，不保證老師電腦的卡頓已解決。

三份環境各自安裝，成績保存在各自的 `data/`，不要同時啟動占用攝影機。本機帳號、成績、`.venv` 及備份 ZIP 不包含在 GitHub 下載中。
