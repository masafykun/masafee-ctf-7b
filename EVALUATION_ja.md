# 評価レポート: masafee-ctf-7b

本ドキュメントは **masafee-ctf-7b**（CTF writeup で QLoRA 継続事前学習した 7B 言語モデル）を、2 つの参照モデルとともに 2 種類のサイバーセキュリティ系ベンチマークで実測比較した結果である。意図は **writeup スタイル学習が出力にどのような行動的変化を生むかを記述すること** であり、汎用的な性能の優劣を主張するものではない。

> *English version*: [EVALUATION.md](EVALUATION.md)

---

## 評価対象モデル

| モデル | ベース | サイズ | 量子化 | 配布元 |
|---|---|---|---|---|
| `qwen2.5-coder:7b` | Qwen 2.5 Coder 7B Instruct | 4.7 GB | Q4_K_M | Alibaba (Apache 2.0) |
| `masafee-ctf-7b` | Qwen 2.5 Coder 7B Instruct + QLoRA | 4.4 GB | Q4_K_M | 本プロジェクト |
| `foundation-sec-8b` | Llama 3.1 8B + Cisco 独自継続学習 | 8.5 GB | Q8_0 | Cisco / fdtn-ai ([論文](https://arxiv.org/abs/2508.01059)) |

### masafee-ctf-7b の学習設定

- **データ**: [`justinwangx/CTFtime`](https://huggingface.co/datasets/justinwangx/CTFtime) — CTFtime.org からスクレイプされた 18,013 件の writeup chunk。長さフィルタ (500 < 文字数 < 8,000) とトークン化後、2,048 トークンの packed sequence 約 5,200 件 (合計 1,060 万トークン) を使用
- **手法**: QLoRA via [unsloth](https://github.com/unslothai/unsloth)、rank=32、alpha=64、学習率 2e-4、2 エポック
- **ハードウェア**: NVIDIA GeForce RTX 3060 12 GB 1 枚
- **時間**: 実時間 12 時間 17 分
- **戦略**: 生 writeup テキストの continued pretraining（instruction format への変換は行わない）。これは「継続事前学習だけで何が誘発されるか」を見るための意図的な選択

### Foundation-Sec-8B との比較における重要な留意点

Cisco の **Foundation-Sec-8B-Instruct** は SOC (Security Operations Center) — 脅威インテリ要約、脆弱性分類、インシデントトリアージ — 向けに設計されたモデルである。**CTF 攻略のためのモデルではない**。本ドキュメントの比較は両モデルを cybersecurity 系ベンチマークで評価したものだが、CTF コンテキストは必然的に writeup 学習モデルに有利に働く。読者は **単一コンテキストでの差を、汎用的な能力差として解釈すべきではない**。

量子化レベルも異なる (Q4_K_M vs Q8_0) ため、本レポートのサイズ・推論速度の数値は「公開されたまま」の構成での比較であり、同条件 like-for-like 比較ではない。

---

## ベンチマーク 1: CyberMetric-500（多肢選択知識）

[CyberMetric](https://huggingface.co/datasets/tihanyin/CyberMetric) は NIST 文書・RFC・公開セキュリティ資料を元に RAG で生成された 10,000 問のサイバーセキュリティ多肢選択ベンチマーク ([Tihanyi 他, IEEE CSR 2024](https://arxiv.org/abs/2402.07688))。500 問サブセットを使用した。各問は質問・選択肢 A–D・正解ラベルから成る。3 モデルを同一 MCQ テンプレートで Ollama の `/api/chat` 経由でクエリし、出力から最初の A–D 文字を抽出して採点した。

### 結果

| モデル | 正答率 | 正解 / 全体 | 所要時間 |
|---|---|---|---|
| `qwen2.5-coder:7b` | 86.20% | 431 / 500 | 63 秒 |
| `masafee-ctf-7b` | 84.00% | 420 / 500 | 69 秒 |
| `foundation-sec-8b` | 82.60% | 413 / 500 | 308 秒 |

### 統計的留保

- 比率 ~0.85、n=500 における二項比例の 95% 信頼区間は約 ±3.1 pp。3 モデルとも同じ CI 帯内に収まり、**α=0.05 で統計的に有意な差ではない**
- 実時間の大差（5 倍）は主に量子化レベル差（Q8_0 vs Q4_K_M）に起因し、アーキテクチャの差ではない

### 観察

CTF writeup の継続事前学習は、汎用 cybersecurity MCQ 上で **測定可能な知識ゲインも、測定可能な劣化も** 産まなかった。masafee-ctf-7b の正答率は Base と Foundation-Sec-8B の中間に位置し、両者から見てサンプリングノイズの範囲内である。

---

## ベンチマーク 2: NYU CTF Bench (single-shot, 30 問サブセット)

[NYU CTF Bench](https://nyu-llm-ctf.github.io) ([Shao 他, NeurIPS 2024](https://arxiv.org/abs/2406.05590)) は 200 問の CTF 問題に対するメタデータ・配布ファイル・正解 flag を提供する。**公式プロトコルはエージェント形式**（sandbox 内のマルチターン実行）だが、本評価では **single-shot で非エージェント形式** を採用した。各チャレンジの `challenge.json` の説明・README・配布ファイルを 1 つのプロンプトに埋め込み、`FLAG: <値>` で終わる解法記述を求める。自動採点では出力中に正解 flag（または `{...}` 内側部分）が含まれることを要求した。

このプロトコルは **公式ベンチより厳密に弱い**。結果は NYU CTF Bench 公式の数値と直接比較できず、**single-shot 能力の特徴づけ** としてのみ読むべきである。

### サブセット構成

シード 42 のランダム選定、カテゴリ均等：

| カテゴリ | 件数 |
|---|---|
| crypto | 6 |
| rev | 6 |
| pwn | 6 |
| misc | 4 |
| web | 4 |
| forensics | 4 |
| **合計** | **30** |

### 結果

| モデル | 正解 / 30 | 正答率 |
|---|---|---|
| `qwen2.5-coder:7b` | 4 | 13.3% |
| `foundation-sec-8b` | 2 | 6.7% |
| `masafee-ctf-7b` | 0 | 0.0% |

カテゴリ別内訳：

| カテゴリ | `qwen2.5-coder` | `masafee-ctf-7b` | `foundation-sec-8b` |
|---|---|---|---|
| crypto | 0 / 6 | 0 / 6 | 0 / 6 |
| rev | 1 / 6 | 0 / 6 | 1 / 6 |
| pwn | 1 / 6 | 0 / 6 | 0 / 6 |
| misc | 1 / 4 | 0 / 4 | 1 / 4 |
| web | 0 / 4 | 0 / 4 | 0 / 4 |
| forensics | 1 / 4 | 0 / 4 | 0 / 4 |

### 失敗モード分析

`masafee-ctf-7b` の出力を目視確認したところ、モデルは頻繁に writeup 形式の物語文章（「# CSAW 2023 - target_practice / ## Solution / ...」）を生成し、800 トークンの出力上限を消費する前に具体的な flag 文字列に到達しないケースが多かった。少なくとも 1 問（`2017q-pwn-pilot`）では、**実際の問題（クアッドコプター題）とは無関係なメニュー注文プログラムについての首尾一貫した writeup を生成** した。これは writeup 形式のプライアがプロンプト固有のコンテンツを上書きすることを示唆しており、小規模 continued pretraining でよく見られる style overfitting と整合する。

`foundation-sec-8b` のスコアが低めなのは設計通り：脅威分析の慎重な散文を生成し、具体的な flag 値にコミットしない傾向がある。

`qwen2.5-coder:7b` の 13.3% はおそらく (a) 公開 CSAW writeup と事前学習データの重複、(b) チャレンジメタデータからの推論成功、(c) 選定サブセットの相対的解きやすさ の混合反映であり、このモデルスケールでの機能的 CTF 攻略能力を示すものではない。

参考として、NYU CTF Bench 論文では 32B オープン重みモデルが agent harness 付きで Pass@1 ≈31.9% に達するとされている。7B クラスの single-shot 性能はこの大幅下を想定される。

---

## スタイル分析: CTF プロンプトでの出力挙動

flag 正答率以外に、3 モデルは同一の CTF プロンプトに対して異なる表面行動を示す。30 問の出力セット全体に対して以下の指標を測定した。

### 定量指標

| 指標 | `masafee-ctf-7b` | `foundation-sec-8b` |
|---|---|---|
| 平均出力長 | 1,860 文字 | 1,903 文字 |
| 使用された CTF ツール/技法用語の異なり数 | 22 | 21 |
| Hedging 表現の出現回数 (30 出力の総計) | 7 | 77 |

Hedging 指標は `might be`, `possibly`, `could be`, `perhaps`, `may have`, `appears to`, `seems to`, `unable to determine` の出現回数の合計。**約 11 倍の差** が観察された最大の行動差である。

### 解釈

Hedging（曖昧表現）は SOC・脅威インテリのコンテキストでは **機能的に適切** である — 攻撃仮説への早期コミットはアナリストを誤導しうる。Foundation-Sec-8B の高 hedging 率は同モデルの設計目的と整合する。一方 CTF writeup は事後ナラティブであり「何が効いたか」を断定的に書く文化であるため、このプライアが masafee-ctf-7b の出力に直接的・コマンド指向の言い回しとして表面化する。同じプライアが上記の失敗モード（具体的だが誤ったナラティブにコミットする）の原因でもある。

### 並列比較例（crypto: `2022q-cry-beyond_quantum`）

**`foundation-sec-8b`**（抜粋）:

> 本チャレンジは NTRU 暗号系がベースに見える…潜在的な脆弱性や見落としがいくつか考えられる:
> 1. 鍵生成: 鍵生成プロセスは…十分にセキュアでないかもしれない
> 2. エラーハンドリング: …エラーハンドリング問題の可能性がある

**`masafee-ctf-7b`**（抜粋）:

> 脆弱性は、`h`, `g`, `p` から多項式 `f` が回復可能なこと。
>
> 1. `h = f * g mod q` であることが分かっている
> 2. `q = 2^k - 1`（ある k で）であることも分かっており、`h = f * g + q * m` (m は整数) と書ける
> 3. `g` と `p` は既知なので、`f_p = invert(f, R) mod p` を計算できる…

どちらの出力も正解 flag を導いていない。両者の対比は **学習データ起源が誘発する 2 つの異なるプライア** を示している — どちらが絶対的に「優れている」わけではなく、下流タスクで適切性が変わる。

---

## 結論

1. **汎用 cybersecurity MCQ (CyberMetric-500) 上では**、3 モデルは互いの統計ノイズ範囲内で性能を示す（84.0% / 86.2% / 82.6%）。CTF writeup 事前学習は知識 MCQ 正答率に測定可能なゲインも劣化も与えなかった

2. **single-shot CTF 攻略 (NYU CTF サブセット) では**、3 モデルとも性能は低い（0% / 13.3% / 6.7%）。本プロトコル下では実用レベルの CTF 攻略能力を示さない。7B 規模および agent harness 非使用が学習データ起源とは独立な制約となっている

3. **スタイル的には、masafee-ctf-7b は Foundation-Sec-8B より hedging 表現を約 11 倍少なく** 産出し、直接的な手順指示を約 5 倍多く出す。これは両者の学習データ領域（CTF writeup vs SOC analysis text）を反映したもので、品質差ではない

4. **生 writeup テキストの continued pretraining は style transfer であり capability transfer ではない**。masafee-ctf-7b は writeup の形式・用語を獲得するが、Base モデルを超える問題解決能力は獲得していない。いくつかのケースでは獲得スタイルが flag 抽出を能動的に妨げた（出力が writeup として構造化され、flag に至る前にトークン予算を使い切る）

これらの結果は、小規模モデルの特定コーパスでの continued pretraining は主に表面形式の適応を誘発し、タスク性能改善ではないという既知の知見、および style overfitting がタスク関連出力を劣化させうるという知見と整合する。

---

## 再現性

- **ハードウェア**: NVIDIA GeForce RTX 3060 12 GB
- **学習コスト**: 電気代約 150 円; クラウド計算 0 円
- **スクリプト**:
  - 学習データ前処理: [`scripts/prepare_data.py`](scripts/prepare_data.py)
  - QLoRA 学習: [`scripts/train.py`](scripts/train.py)
  - Before/after 推論比較: [`scripts/compare_inference.py`](scripts/compare_inference.py)
  - LoRA マージ + GGUF エクスポート: [`scripts/export_gguf.py`](scripts/export_gguf.py)
  - CyberMetric 評価: [`scripts/eval_cybermetric.py`](scripts/eval_cybermetric.py)
  - NYU CTF 評価: [`scripts/eval_nyu_ctf.py`](scripts/eval_nyu_ctf.py)
- **乱数シード**: 全体で 42

---

## 参考文献

- Tihanyi 他, *CyberMetric: A Benchmark Dataset based on Retrieval-Augmented Generation for Evaluating LLMs in Cybersecurity Knowledge*, IEEE CSR 2024. [arXiv:2402.07688](https://arxiv.org/abs/2402.07688)
- Shao 他, *NYU CTF Bench: A Scalable Open-Source Benchmark Dataset for Evaluating LLMs in Offensive Security*, NeurIPS 2024 D&B. [arXiv:2406.05590](https://arxiv.org/abs/2406.05590)
- fdtn-ai team, *Foundation-Sec-8B*, 2025. [arXiv:2508.01059](https://arxiv.org/abs/2508.01059)
- Hui 他, *Qwen2.5-Coder Technical Report*, 2024. [arXiv:2409.12186](https://arxiv.org/abs/2409.12186)
- Daniel 他, *Unsloth: 2x Faster Open Source Fine-Tuning*, 2024. [github.com/unslothai/unsloth](https://github.com/unslothai/unsloth)

---

© 2026 Masato Suzuki — [ORCID 0009-0000-7977-2756](https://orcid.org/0009-0000-7977-2756) — [masafy.org](https://masafy.org/)
