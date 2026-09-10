# CUMCM-2026

2026 国赛 C 题协作仓库。当前阶段：Q1 方案与独立核验基线，正式实现交给 fable。

## 先读

1. docs/q1_spec.md：第一问数学、单位、时间轴、输出合同。
2. prompts/fable_q1.md：可直接交给 fable 的任务提示词。
3. docs/q1_acceptance.md：独立验收标准。
4. docs/git_workflow.md：分支同步、检查点与回滚。
5. docs/status.md：当前完成情况与下一步。

## 目录

- data/raw/：题面、附件1—4，只读原始材料。
- data/templates/：五个原始模板，只读。
- data/manifest.json：原始文件 SHA-256。
- configs/：问题参数；当前 q1.json。
- src/microgrid/：正式求解与导出代码，由 fable 实现。
- tests/：正式实现测试；tests/review/ 为审查方的核验器测试。
- review/：独立读取原始数据、LP参考下界和结果核验，不依赖正式求解代码。
- outputs/q1/：fable 的第一问正式结果。
- reports/q1/：验收报告与解释。
- docs/、prompts/：方案、协作规范与执行提示词。

不提交 .venv、凭据、Excel锁文件、缓存。原始输入和通过核验的最终结果保留在Git中。
不要预先扩展Q2—Q4代码；现阶段先让Q1结果可重复、可检查。

## 环境与已有命令

Python 3.12；Windows和Linux均使用仓库相对路径。

~~~bash
python -m venv .venv
# Windows: .venv\Scripts\python.exe
# Linux:   .venv/bin/python
python -m pip install -r requirements-lock.txt
python review/q1_reference.py --output review/artifacts/q1_reference.json
python -m pytest tests/review -q
~~~

正式实现完成后增加：

~~~bash
python -m pip install -e .
python -m microgrid.q1 --config configs/q1.json --output outputs/q1
python review/verify_q1.py --run outputs/q1 --report reports/q1/verification.json
~~~

独立参考结果不等于已完成 result1.xlsx。模型、文件和数据通过独立核验后才能标记 Q1 完成。
