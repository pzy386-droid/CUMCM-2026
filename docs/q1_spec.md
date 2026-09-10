# Q1锁定规格 v1

## 目标与边界

依据题面Q1、附录1、附件1和result1原始模板，完成单日确定性经济调度。
不进行预测训练、随机情景、MPC、Q2紧急购电、Q3调整费用或Q4实时电价。
附录初值作为主口径：S0=S144=6000kWh，不设自由初值，不预先强制两充两放。
正式求解使用MILP；独立LP放松只作参考下界，若其本身也满足全部约束，可构成最优性佐证。

## 数学

t=1,...,144，Δ=1/6h，ℓ_t=L_tΔ，q_t=PV_tΔ，M=5000Δ=833.333333...kWh。
g、c、d、r分别是母线侧购电、充电、放电、富余未利用电量；S为储电量；z为0/1模式。
目标 J=min Σ p_t g_t。

- g_t+q_t+d_t=ℓ_t+c_t+r_t。
- S_t=S_(t-1)+0.9c_t-d_t/0.9。
- 1200≤S_t≤10800，对t=0,...,144全部检查。
- S0=S144=6000。
- 0≤c_t≤M z_t；0≤d_t≤M(1-z_t)。
- g_t,r_t≥0；无售电、无应急购电。
- 延续统一执行规范，r_t≤R_t z_t，避免放电后弃掉电量。
- 为有限上界取 G_t=ℓ_t+M，0≤g_t≤G_t，R_t=G_t+q_t；该上界来自正价格下本段负载与最大充电需求，不是新增外网设备容量。

说明：充电取走c，入电池0.9c；电池送出d，内部消耗d/0.9。
两端各90%对应往返81%；往返90%的敏感性可另外跑，但不能覆盖主结果。
r表示总富余未利用量，不能在未分解来源时全部称“弃光”。

## 时间与模板

输入每个时间点解释为前一个十分钟区间的右端，值作为该区间代表功率。
内部第1段00:00—00:10，第144段23:50—24:00；时段开始和结束用HH:MM，允许24:00。
输入原始表第2行是第1段，第62行是10:00—10:10。
六个指定段索引（1基）：61、73、85、97、109、121。

原模板标签错位：A2写0:10-0:20，A145写0:00+1-0:10+1。
正式输出保留两个工作表、原字段结构，在输出副本中修正A2:A145为完整当天区间。
禁止改变原模板文件。提供template_mapping.csv记录原标签、正确标签与输入行。
不要按旧标签对数值二次平移；不能声称修正后的标签仍与错误原件逐字相同。

“计划购电量”：仅A1:B145；A1=时间段、B1=购电量；A2:A145使用00:00-00:10...23:50-24:00；B列对应g_t。
“充放电量”：仅A1:E7；表头原样保留；A2:A7原有六个4小时段标签原样保留；B/C分别是c/d每24段之和；D2/D3保留0:00/24:00；E2/E3为6000。
其他模板空白格保持空白。无新增工作表、行或列。总费在summary.json和论文表1中给出，不擅自扩展result1模板。

## 输出合同

outputs/q1/必须有：

1. schedule.csv，UTF-8，144行，不计表头；列顺序严格为：
   slot,start,end,price_yuan_per_kwh,load_kw,pv_kw,grid_kwh,charge_kwh,discharge_kwh,spill_kwh,soc_start_kwh,soc_end_kwh,cost_yuan
   slot为1...144；全精度；cost_yuan=p×g；每行保留输入功率和电价。
2. summary.json：
   schema_version=1；
   objective_yuan、total_grid_kwh、total_charge_kwh、total_discharge_kwh、total_spill_kwh、soc_initial_kwh、soc_final_kwh；
   input_sha256、template_sha256；
   solver={name,status:"optimal",mip_gap,wall_seconds}，求解器未证最优不可谎填optimal；
   source_git_commit（运行时的代码提交）、source_dirty（布尔值）；
   输出由一次运行生成，不互相手改。
3. result1.xlsx：上述两表结构，数值全精度存储，显示两位小数。
4. template_mapping.csv：144行，列为
   slot,input_excel_row,template_label_cell,original_label,corrected_label。
   如首行1,2,A2,0:10-0:20,00:00-00:10。
5. tables_q1.md：表1六段g、全天购电量、全天购电费；表2六个4小时块充放电、首尾S。
6. run_metadata.json或summary的补充字段：Python、NumPy、SciPy、Excel库版本；解的数值容差；参数；命令；耗时。
7. figures/可选：调度图与SOC图。先保证数值与表格正确再画图。

正式结果不要求逐点等于参考LP解：可能存在多重最优解。应检查可行性及费用证书。

## 求解与验收

建议 scipy.optimize.milp / HiGHS，稀疏矩阵；返回status与mip_gap必须记录。
https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html

初版只最小化真实购电费。若增加去除退化解的二级目标，采用字典序/固定首目标容差，并披露，不能悄悄加入电池寿命成本。
数值残差阈值：能量和SOC 1e-6kWh；费用比较 max(1e-5元,1e-8×参考费用)。
MILP期望gap≤1e-8。先记录全精度，再设置显示格式；不能逐段四舍五入后累计。

独立审查方review/q1_reference.py重新读取附件，独立构建更宽松LP，不导入正式模型代码。
review/verify_q1.py检查CSV、summary、原始数据hash、XLSX读回、映射、物理和费用，再比较LP下界。
若MILP费用高于LP下界，先调查，不强行写错结果过检；提供MILP证明和差距供审查决定。
