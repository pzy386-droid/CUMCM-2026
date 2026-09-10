# CUMCM-2026

2026国赛C题协作仓库。用户已确认Q1完成，当前阶段为Q2规格交接与实现准备。

## 第二问从这里开始

- [交接入口与原始材料](docs/q2/README.md)
- [最小信息主干](docs/q2/outline.md)
- [数学模型与执行器](docs/q2/model.md)
- [数据与因果边界](docs/q2/data_and_causality.md)
- [实施顺序与实验](docs/q2/implementation.md)
- [输出合同](docs/q2/output_contract.md)
- [验收清单](docs/q2/acceptance.md)
- [给fable的精简提示词](prompts/fable_q2.md)

当前分支codex/q2-spec-review包含Q1完整实现及Q2交接文档，尚未实现Q2生产代码。fable从q2-spec-v1建立codex/q2-implementation。
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
