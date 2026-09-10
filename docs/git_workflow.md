# Git协作与回滚

仓库：https://github.com/pzy386-droid/CUMCM-2026
本地建议：C:\Users\yoyo\Desktop\12\CUMCM-2026（代码不得硬编码本机路径）。

## 分支与职责
- main：稳定共享版本，暂保留初始提交。
- codex/q1-spec-review：方案、输入、独立参考与核验器。
- codex/q1-implementation：fable正式实现，从q1-spec-v1标签起步。
- 如该实现分支已存在，先fetch、检查历史和工作区，再在该分支继续，不重建或强制覆盖。

首次接手：
~~~bash
git clone https://github.com/pzy386-droid/CUMCM-2026.git
cd CUMCM-2026
git fetch origin --tags
git switch -c codex/q1-implementation q1-spec-v1
~~~

同一电脑已有checkout时，优先另建工作树，避免两个角色互相切分支：
~~~bash
git worktree add ../CUMCM-2026-fable -b codex/q1-implementation q1-spec-v1
~~~
远端已有分支时先按git状态调整为跟踪已有分支，不能盲目重复执行-b。

## 原子检查点
1. spec：规格、输入、独立核验；标签q1-spec-v1。
2. model：正式求解与生产单元测试；提交后再生成可追溯结果。
3. results：账本、result1、论文表与运行元数据。
4. review：独立核验和代码审查报告。
5. accepted：审查通过后才打q1-accepted-v1并合并main，本轮不提前打。

每次：
~~~bash
git status --short
git diff --check
git add <明确的文件列表>
git commit -m "<说明这一批的具体变化>"
git push -u origin <当前功能分支>
~~~
输出的source_git_commit记录求解代码提交，生成结果时输出目录变动不等于模型代码变动。

## 同步审查更新
~~~bash
git fetch origin --tags
git merge origin/codex/q1-spec-review
~~~
冲突先阅读两边；规格冲突不得自行删除规则来“解决”。

## 回滚
保留共享历史，用git revert逐个撤销已确认有问题的提交，再普通push。
若只想查看旧版本，用git worktree add ../q1-inspect q1-spec-v1创建独立检视目录。
不执行reset --hard、clean -fd或force push覆盖他人工作。
不要把.git、.venv、密钥、环境文件和Excel锁文件放进提交。
