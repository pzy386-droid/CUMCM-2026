# 实现规划与求解纪律

## 1. 文件规划

保留 Q1/Q2 原代码和结果。可复用已读过的 `q2_data.py`、`q2_physics.py` 的公共逻辑，但不得为了 Q3 改坏 Q2 默认行为。新增建议：

```text
configs/q3.json                  主版：no_refund_final_vs_original
configs/q3_refund.json           退款敏感性，独立重优化
src/microgrid/q3_forecast.py     发布时刻访问器、插值、版本残差
src/microgrid/q3_contract.py     g0与修订版本、冻结、独立结算
src/microgrid/q3_model.py        日前/剩余日MILP、候选评分
src/microgrid/q3_simulate.py     因果时钟、跨日执行、快照
src/microgrid/q3_export.py       四表、论文表、读回
src/microgrid/q3.py              CLI、版本绑定、原子发布
tests/production/test_q3_*.py    生产测试
reports/q3/                     preflight、审查/实验摘要
outputs/q3/<run_id>/             原始运行产物（不散装提交Git）
```

审查方维护 `review/` 和 `tests/review/`。fable 可用独立手算用例检查实现，但不得改审查预期值来适配自己的输出。若发现题意矛盾，给题面位置、反例和替代方案；普通实现细节按本规格自行处理。

## 2. 时序伪代码

```text
for D in Jan1..Dec31:
    S = previous_real_end_SOC
    reveal forecast(D,00:00); build only historical information
    create Nhat0, source_day_ids, scenarios_00
    solve g0 and policy; validate; freeze g0 and initial snapshot
    for k in 0..143:
        if k in {36,72,108}:
            reveal exactly the newly available forecast
            build current-vintage scenarios on same source dates
            solve remaining a, policy with true S and frozen g0
            validate; compare candidate vs keep through scenario projection
            accept or keep; record a fresh immutable snapshot
        freeze effective a[k] before seeing actual interval k
        observe actual L[k],P[k]; calculate eps against Nhat0
        project policy; update S; settle final-vs-g0 cost once
        append immutable ledger row
    append matured residuals for completed day D
    persist progress and recoverable state
```

1/1负载无历史：沿用 Q2 保守启动 g=0、储能保持6000，当日不执行有经济意义的优化修订，记录 `cold_start_no_load_history`；四次预报照常归档，实际净缺口应急补足。此例外是一月启动规则，不是跳过提交期内的预报。1/2起有历史即按主算法运行。

## 3. 超时、异常与保护

Q2中30秒限时曾在CPU争用下无可行解。不能承诺“单核运行就必然精确复现”。单进程无其他求解争用，固定并记录实际线程数；采用本地预检得到的时间预算，默认候选预算可从日前30s、日内15/10/5s起步，**不得未经Q3预检照搬为最终全年配置**。

预检比较30/60秒等配对同一问题，选择合理预算后固定。线程参数若 scipy 接口不支持，要显式处理/验证实际后端设置，不能只写一个未生效环境变量冒充锁定。不要同时跑多个全年实验争抢同一组核心。

严格检查有限数、线性约束、变量界、互斥与尾部；仅 `optimal` 或经过可行性检查的 `time_limit` 候选可用。记录dual bound和gap，不能把time_limit标为optimal。超时无候选与存在合法限时解分开。

日前无合法候选：因果回退 g=max(当前点预测净负荷,0)，x=0；日内无合法候选：保留原有效合同和规则，再作逐段物理投影。回退不是隐含缺供，也不能用当天真实未来重新求解救场。可实现确定性可行启发式作为备选，但必须同样记录且不私改优化目标。

每个阶段记录模型构造时间、求解时间、guard评价时间、参数和矩阵哈希。复算同一已归档策略不应再次调用限时优化器；先实现 `replay_saved_policies`，用固定快照重现原账本。这能把执行错误与求解器重新搜索差异分开。

## 4. 四个交付关卡

1. 数据与结算：完整预报索引、手算与时间边界通过；先提交代码。
2. 小问题与回归：MILP/执行/guard/输出人工例，Q1/Q2回归通过。
3. 连续20日预检与边界例：按因果顺序从1/1起步；另覆盖2/1衔接、12/31跨年预报、价格变化段与极端SOC。保存真实耗时、gap、fallback、accept统计，核实没有代码假设被违反。参数只能用一月/更早窗口选择。
4. 固定代码和配置后顺序跑全年；先一条主run，验收及归档可恢复后再跑消融，不并发堆年度作业。新发现若只是排版修复优先从固定账本重新导出，不无意义地重求365天MILP。

这些关卡减少可避免的返工，不是“以后绝不需要重跑”的保证。代码/数学错误影响决策时，仍必须重新生成受影响的因果轨迹并标明旧结果失效。
