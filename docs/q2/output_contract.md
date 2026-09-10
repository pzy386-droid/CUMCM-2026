# Q2 输出合同

## 一份账本

正式评估2025-02-01至12-31：334天×144=48096行；另保留全年365天×144=52560行以验证冷启动衔接。
底层全精度保存；Excel和论文显示两位小数，不先舍入再求和。

推荐目录outputs/q2/<run_id>/：
- ledger_full_year.csv、ledger_submission.csv；
- daily_summary.csv、emergency_events.csv；
- forecast_archive/、scenario_manifest/、policy_snapshots/；
- solver_log.csv、summary.json、run_metadata.json；
- template_mapping.csv、result2.xlsx、tables_q2.md、figures/。

逐段账本必含：
date、slot、start、end；
price_yuan_per_kwh、load_kw、pv_kw；
日前预测和预测版本；
planned_grid_kwh、emergency_grid_kwh；
charge_kwh、discharge_kwh、spill_kwh；
soc_start_kwh、soc_end_kwh；
planned_cost_yuan、emergency_cost_yuan、total_cost_yuan；
policy_id、x_raw_kwh、x_executed_kwh、projection_delta_kwh；
fallback及原因。
若保留effective_grid_kwh，必须始终等于planned_grid_kwh。

daily_summary保存计划电量、应急电量、实际总购入g+e、三项费用、充放电/富余、首末SOC、事件数、投影/回退统计。现金汇总不包含虚拟尾部费用。
summary记录正式334天总体指标、四指定日、初末资源和所有异常统计。保留一月费用但不混入正式334天主总费用。

run_metadata必含schema_version、run_id、状态、代码SHA、source_dirty、配置内容及SHA、输入与模板SHA、依赖版本、真实命令、开始/完成时间、种子、数据截止规则、观测解释、情景和求解参数、实际输出清单。
命令与路径以仓库相对写法记录；不要提交个人绝对路径、凭据或环境文件。

## result2.xlsx

原始模板data/templates/result2.xlsx不可修改。正式副本只含原顺序三表：
计划购电量、充放电量、紧急购电量。

### 计划购电量

335行×147列：
- 日期334行完整且有序；
- 第2—145列填144段0时合同g；
- 第146列填Σg；
- 第147列填完整J2=Σpg+Σ5pe。

最后一列采用总费用是本项目明确解释；在导出说明注明，费用分项存daily_summary，不增加模板列。
第一段标签修正为00:00-00:10，末段23:50-24:00。原模板错位，输出不可能同时保持原错标签和正确语义；只修正副本。
template_mapping逐列记录原标签、修正标签、内部t和输入对应位置。附件2第t+1列对应时段t；六指定段t=61/73/85/97/109/121。

### 充放电量

6列：日期、时间段、充电量、放电量、时刻、储电量。
原模板含省略号，展开为2004行数据＋表头=2005行。
每日期6行、每行汇总24段；日期按模板日分组首行填写，其余留白。
每组首两行时刻分别0:00、24:00，对应真实首末S，其余状态格留白。
不可每天填6000；跨日两端必须相等。

### 紧急购电量

保留3列：日期、购电时间段、购电量；事件行数动态展开。
同日相邻正e合并，零间隔断开，不跨日。事件电量由全精度e求和。
每段费用按自己的p计算，不能取事件首价乘事件总量。
建议正事件判定tol_event=1e-9kWh，另检查按日合并前后差≤1e-6kWh，并报告被容差归零的合计；费用仍用原始e，不能静默丢失实质电量。
无事件日期保留日期、空时段、0电量，明确该行是“无事件”占位而非事件；该行不参与事件次数。
清除所有省略号与模板示例占位；不按模板原行数截断事件。

## 论文表格

四日期：2025-03-20、06-21、09-23、12-21。
每日期按题面表1、表2排版，表3按四日期并列事件列组排版：
- 表1每行三组“时间段/购电量”，两行覆盖六指定段，表内附全天购电量和费；
- 表2每行两组“时间段/充电量/放电量”，三行覆盖六个4小时块，表内附首末储电量；
- 表3列四日期的紧急事件及量。
Markdown不能表达的合并单元格可在最终论文排版处理，但列组与内容必须对齐题面。
不能把内部行号和时段索引作为论文主表列。

论文表1主购电量采用实际总购入g+e，表注明“计划合同＋紧急购电”；另列g/e分项明细。
这与Excel计划表只填g不同，必须说明，不能把两者混成一个未定义的购电量。

## 图件与一致性

可选图：指定日价格/负载PV/合同与应急/充放电/SOC；全年日费用与应急统计。
kW与kWh坐标分清；阶梯曲线用145边界覆盖完整24小时，不漏最后10分钟。
图只读账本，不重新求解另一条曲线；绘图依赖显式列为可选环境并记录版本。
所有图、表、Excel由同一run_id账本产生，出错时不拼接旧文件。
