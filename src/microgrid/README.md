# microgrid — 正式代码（fable）

问题1实现，数学口径以 docs/q1_spec.md 为准。

| 模块 | 职责 |
|---|---|
| `inputs.py` | 读取 data/raw/附件1.xlsx，时间对齐（输入时间戳 = 前一个十分钟区间的右端；第2行 = 第1段 00:00-00:10；第62行 = 第61段 10:00-10:10），SHA-256 |
| `model_q1.py` | 稀疏 MILP（scipy.optimize.milp / HiGHS）：母线侧 g/c/d/r，S_t = S_(t-1) + 0.9c_t − d_t/0.9，1200≤S≤10800，S0=S144=6000，c/d≤5000/6，z 二元互斥且 r_t≤R_t z_t；求解后自检物理约束 |
| `export_q1.py` | 由同一逐段账本生成 schedule.csv、template_mapping.csv、result1.xlsx（模板副本，A2:A145 修正为 00:00-00:10 … 23:50-24:00，数值全精度、显示两位小数）、tables_q1.md |
| `figures_q1.py` | 可选图件：figures/schedule.png（电价、负载/光伏/购电功率、充放电条形图，三面板共用时间轴，不用双轴）与 figures/soc.png（储电量轨迹、上下限、首末 6000）；只读账本，不重解；matplotlib 缺失时跳过并在 run_metadata 记录 |
| `q1.py` | CLI：`python -m microgrid.q1 --config configs/q1.json --output outputs/q1`；写 summary.json 与 run_metadata.json（求解状态、gap、版本、代码提交 SHA、dirty 标记） |

运行方式（仓库根目录）：

~~~bash
pip install -e .            # 或临时 PYTHONPATH=src
python -m microgrid.q1 --config configs/q1.json --output outputs/q1
python -m pytest -q         # tests/production 为正式测试，tests/review 由审查方维护
python review/verify_q1.py --run outputs/q1 --report reports/q1/verification.json
~~~

约定：

- 所有数值全精度写入 CSV/JSON/xlsx；只有 Excel 显示格式和 tables_q1.md 使用两位小数。
- `source_dirty` 表示运行时 src/、configs/、pyproject.toml、requirements-lock.txt 下存在未提交改动（含未跟踪文件）；outputs/ 不计入。
- 求解器未证最优（状态非 optimal 或 gap 超限）时直接失败，不写任何结果文件。
- 核验代码在 review/，与本包互不导入。
