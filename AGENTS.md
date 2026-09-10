# 协作边界

- 用户已确认采用 docs/references/融合方案与审查.md；Q1的具体实现合同以 docs/q1_spec.md 为准。
- 审查负责人维护 docs/、review/、tests/review/。fable负责 src/microgrid/、正式实现测试及 outputs/q1/。
- fable发现规格或核验器错误，应记录复现证据并交回审查；不要为了让检查通过而改核验口径。
- data/raw/、data/templates/、data/manifest.json禁止无说明修改；不读Q2—Q4数据来拟合Q1。
- 当前只实施Q1。使用相对路径，不写个人绝对路径或凭据进仓库。
- 数值全精度保存，显示两位小数。所有报告从同一逐段账本生成。
- 主分支main不直接改写。功能分支普通push；不用force push、reset --hard、clean -fd覆盖他人工作。
- 使用提交与标签作为检查点。共享历史用revert回滚；不要重写已同步历史。
- 交付必须报告实际运行的命令、求解状态和失败项，不声称未执行的检查已通过。
