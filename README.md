# CUMCM-2026

2026国赛C题协作仓库。当前：Q2文件级审查已完成、完整运行归档待验；Q3规格交接，尚未实现Q3。

## 第三问从这里开始

- [Q3交接入口](docs/q3/README.md)
- [给fable的提示词](prompts/fable_q3.md)
- [Q3最小提纲](docs/q3/outline.md)
- [Q2独立审查及必须修正的问题](reports/q2/astra_review.md)

本交接在codex/q3-spec-review，检查点q3-spec-v1。已继承收到的Q2代码历史c10be27；Q2的旧报告不因进入本分支而自动通过审查。GitHub默认main不会自动合入本分支。

## 第二问从这里开始

- [交接入口与原始材料](docs/q2/README.md)
- [最小信息主干](docs/q2/outline.md)
- [数学模型与执行器](docs/q2/model.md)
- [数据与因果边界](docs/q2/data_and_causality.md)
- [实施顺序与实验](docs/q2/implementation.md)
- [输出合同](docs/q2/output_contract.md)
- [验收清单](docs/q2/acceptance.md)
- [给fable的精简提示词](prompts/fable_q2.md)

以上为历史Q2交接入口；当前实现及审查以docs/q2/review_addendum.md为准。
GitHub默认main不会自动显示其他分支的新文档，请打开相应分支。

## 目录

- data/raw、data/templates：只读原始题面、数据、模板；data/manifest.json核对SHA。
- src/microgrid：正式实现；tests/production：生产测试。
- review、tests/review：审查方独立核验，目前主要针对Q1。
- outputs/q1：第一问结果；Q2使用outputs/q2/<run_id>。
- reports：运行、实验与审查记录；docs、prompts：方案与交接。

## Q1复现

Python及依赖见requirements-lock.txt。先激活虚拟环境，再运行：

```bash
python -m pip install -r requirements-lock.txt
python -m pip install -e .
python -m microgrid.q1 --config configs/q1.json --output outputs/q1
python -m pytest -q
python review/verify_q1.py --run outputs/q1 --report reports/q1/verification.json
```

matplotlib为已有绘图功能的可选依赖；没有时可复现数值，绘图会跳过。记录实际环境，不声称未执行的绘图或验收通过。
Q2实现与CLI要求见docs/q2，不用Q1固定参数核验器验证Q2。
