# Q2 交接入口

用户已确认第一问完成，现进入第二问。当前包是规格交接，不代表Q2代码或全年结果已经实现。

基线：远端main的第一问实现 `76e7fbc1a811597531a73ced24f44b778f5a4108`。
交接分支：`codex/q2-spec-review`；交接标签：`q2-spec-v1`。
实现分支：`codex/q2-implementation`，从此交接标签建立，而不是从旧Q1规格标签建立。

## 完整阅读顺序

1. 根目录AGENTS.md及原始[data/raw/C题.pdf](../../data/raw/C题.pdf)。
2. [outline.md](outline.md)：任务主干与不可遗漏事项。
3. [model.md](model.md)：数学、反馈规则、投影和终端价值。
4. [data_and_causality.md](data_and_causality.md)：预测、历史误差、信息可用性。
5. [implementation.md](implementation.md)：模块、求解失败、阶段与实验。
6. [output_contract.md](output_contract.md)：账本、Excel、论文表和运行元数据。
7. [acceptance.md](acceptance.md)：测试和验收边界。
8. [fable提示词](../../prompts/fable_q2.md)及现有Q1源码、测试。

原始数据与模板已在当前Git基线中，无需另传：
- [附件1](../../data/raw/附件1.xlsx)：Q2只取价格。
- [附件2](../../data/raw/附件2.xlsx)：365日负载、实际光伏。
- [result2原始模板](../../data/templates/result2.xlsx)。
- [原始文件哈希](../../data/manifest.json)。

原[总体融合方案](../references/融合方案与审查.md)保留为背景。该历史文件中“求解器尚未安装”等阶段性记录已过时，以当前阶段记录为准。Q2具体实现以本目录为准；实质题意冲突需列证据交回，不以本文件压过题面。

## 明确主线

日前固定合同 → 联合误差情景 → 共享因果储能规则 → 当前物理投影 → 真实费用回放。

Q1的物理与账本是基础；Q2研究不确定性和5倍应急成本。日内可更新储能控制，合同不能改。后续Q3再增加预报与合同调整权限，Q4再改变价格信息与优化目标；本轮不提前实现后两问。

## 接手Git

先检查工作区与已有实现分支，再执行适合当前状态的命令：

```bash
git fetch origin --tags
git switch -c codex/q2-implementation q2-spec-v1
```

共享电脑可从已有仓库另建worktree；分支已存在时继续已有分支，不重复创建、不强制覆盖。实现完成普通push到实现分支。共享回滚用revert，不用force push或reset --hard。交接文件放在功能分支；GitHub默认main不自动显示该分支的新文件。
