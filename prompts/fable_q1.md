你是本项目第一问的代码实现负责人 fable。我负责数学规格与独立审查。请开始实际实现Q1，不要仅回复计划，不扩展Q2—Q4。

仓库：https://github.com/pzy386-droid/CUMCM-2026
先git fetch origin --tags，从q1-spec-v1建立codex/q1-implementation；若分支已存在先检查并继续。和审查方共用电脑时使用独立worktree，避免切换对方工作目录的分支。

先完整阅读：AGENTS.md、docs/q1_spec.md、docs/q1_acceptance.md、docs/git_workflow.md、data/raw/C题.pdf的Q1/附录/模板说明，以及附件1和result1模板。较长的总体融合方案作背景，以Q1规格为准。发现矛盾先记录具体证据，不能悄悄改数学或验收器。

任务：
1. 在src/microgrid中实现可重复运行的Q1 CLI：
   python -m microgrid.q1 --config configs/q1.json --output outputs/q1
2. 144个十分钟段，所有决策为kWh，母线侧c/d；S_t=S_(t-1)+0.9c_t-d_t/0.9；1200≤S≤10800；S0=S144=6000；c/d≤5000/6。
   min Σp*g；g+PV/6+d=L/6+c+r；购电/富余非负；二元模式禁止同时充放电，并按规格禁止放电后弃掉。用稀疏MILP求解，记录状态与最优间隙。
3. 输入00:10作为首段右端标签。输出首段00:00-00:10、末段23:50-24:00。
   原始模板有错位，只修正输出副本标签；原始输入/模板不得改。10:00-10:10是t=61、输入第62行。完整输出映射。
4. 严格按规格生成schedule.csv、summary.json、result1.xlsx、template_mapping.csv、tables_q1.md及运行元数据。底层数值不舍入，Excel显示两位小数；只保留原模板两个工作表和尺寸。
5. 写必要的生产测试：非标准时间字符串、效率、初末状态、互斥、指定段索引、导出读回及求解失败处理。不要硬编码参考答案。
6. 先运行正式测试，再运行独立核验：
   python -m pytest -q
   python review/verify_q1.py --run outputs/q1 --report reports/q1/verification.json
   review/及tests/review由审查方维护，不得改它们让结果过关；若发现核验器有错，提交最小复现供审查。
7. 第一批提交正式模型与测试，第二批提交结果和运行记录；在功能分支普通push。不得直接推main或force push，不覆盖其他人的修改。
8. 最后给出：分支名、各提交SHA、实际运行命令、求解器状态/gap、总购电量/费用、首尾S、独立核验状态、六个指定时段结果、遗留问题。全部事实来自真实运行，未完成项明确写出。

原始材料在data/raw和data/templates，sha见data/manifest.json；所有路径必须相对仓库。先使用已提供依赖锁，新增依赖需明确记录。
review/artifacts中的参考仅用于核验，不是你的正式result1。可能多重最优，不要求每段与参考逐点相同，但物理可行性和最优费用必须被证明。

数学边界：本问没有预测训练、紧急购电费、调整费、跨年仿真、情景随机规划、遗传算法或自由初始SOC。不要预先强制“两充两放”；由结果决定调度结构。
