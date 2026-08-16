# REW 轉 AutoEQ

把 [REW](https://www.roomeqwizard.com/)（Room EQ Wizard）的頻率響應匯出檔，轉成 [AutoEQ](https://autoeq.app) 可以直接讀取的 CSV。

REW 匯出的量測檔是純文字檔，通常會包含 `* ...` 開頭的註解行，以及 `Freq(Hz), SPL(dB), Phase(degrees)` 這類欄位。AutoEQ 則預期一個只有 `frequency,raw` 兩欄、數值是相對 dB 的 CSV。這個工具負責兩者之間的轉換：讀取 REW 匯出檔、過濾頻段、內插到對數間隔的頻率格點、可選的分數倍頻程平滑、轉成相對 dB，最後輸出 AutoEQ 可用的 CSV。

## 功能

- 解析 REW 文字匯出檔（逗號或 Tab 分隔，有無標題列都可以）
- 支援常見編碼，包含 UTF-8、Big5、GB18030
- 可限制輸出頻段（預設 20 Hz - 20 kHz）
- 內插到 1/20 倍頻程的對數頻率格點，符合 AutoEQ 資料慣例
- 可選分數倍頻程高斯平滑（`--smooth 1/3`、`1/6` 等）
- 正規化模式：平均（預設）、中位數、指定參考頻率、或不正規化
- 支援批次轉換（`--output-dir`）
- 純 Python 標準函式庫，無額外依賴

## 安裝

不需要安裝也能直接跑：

```bash
python rew_to_autoeq/cli.py measurement.txt
```

安裝成指令列工具：

```bash
pip install git+https://github.com/xup61069/rew-to-autoeq.git
```

安裝後可使用：

```bash
rew2autoeq measurement.txt
```

## 使用方式

```bash
rew2autoeq <input.txt> [options]
```

範例：

```bash
# 基本轉換；預設在輸入檔旁邊產生 <input>_autoeq.csv
rew2autoeq measurement.txt

# 指定輸出檔
rew2autoeq measurement.txt -o my_eq.csv

# 1/3 倍頻程平滑
rew2autoeq measurement.txt --smooth 1/3

# 以 1 kHz 為 0 dB 做正規化
rew2autoeq measurement.txt --normalize reference --reference-freq 1000

# 批次轉換整個資料夾
rew2autoeq *.txt --output-dir converted/

# 保留原始絕對 SPL 數值和原本頻率解析度
rew2autoeq measurement.txt --no-normalize --no-interpolate
```

## 主要選項

| 選項 | 說明 |
| --- | --- |
| `-o, --output` | 輸出 CSV 路徑（只能用在單一輸入檔） |
| `--output-dir` | 批次轉換的輸出資料夾 |
| `--smooth OCTAVES` | 分數倍頻程平滑寬度，例如 `1/3`、`1/6`、`0.3` |
| `--normalize MODE` | `mean`、`median`、`reference` 或 `none`（預設 `mean`） |
| `--reference-freq HZ` | 搭配 `--normalize reference` 使用的參考頻率 |
| `--min-freq HZ` | 保留的最低頻率（預設 20） |
| `--max-freq HZ` | 保留的最高頻率（預設 20000） |
| `--steps-per-octave N` | 內插格點解析度（預設 20） |
| `--no-interpolate` | 保留 REW 原始頻率解析度 |
| `--quiet` | 只印出轉換後的檔案路徑 |
| `--version` | 顯示版本 |

## 輸出格式

產出的 CSV 只有兩欄：

```csv
frequency,raw
20.00,0.89
20.71,0.98
...
```

把這個檔案上傳到 [autoeq.app](https://autoeq.app)，就可以產生 parametric EQ 設定。

## 從 REW 匯出

在 REW 中使用 **File > Export > Measurement text file**（或你使用版本的對應匯出選項）。預設的逗號分隔匯出檔可以直接使用，不需要特別設定。

## 開發與測試

```bash
python -m unittest discover -s tests -v
```

## License

MIT

