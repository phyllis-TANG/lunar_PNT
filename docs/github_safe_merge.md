# GitHub 安全合并流程

本项目使用“独立分支 + Pull Request”把研究文档、PPT 和后续代码合入 GitHub。不要直接向 `main` 或 `master` 强制推送，也不要使用 `--force` 覆盖远端历史。

## 1. 登录并读取远端

云端环境必须先具有 GitHub 凭据。推荐使用 GitHub CLI：

```bash
gh auth login
gh auth setup-git
git fetch origin --prune
```

登录后先确认默认分支和远端状态：

```bash
gh repo view phyllis-TANG/lunar_PNT --json defaultBranchRef
git branch -r
git log --oneline --decorate --graph --all -20
```

## 2. 从最新默认分支建立工作分支

假设默认分支是 `main`：

```bash
git switch main
git pull --ff-only origin main
git switch -c docs/roscar-uwb-plan
```

如果默认分支是 `master`，把以上命令中的 `main` 全部替换为 `master`。`--ff-only` 会在本地与远端历史分叉时停止，而不是自动制造难以检查的合并提交。

## 3. 引入已经完成的本地提交

当前文档和 PPT 位于本地 `work` 分支。应从最新远端默认分支创建新分支，然后逐个挑选提交，而不是把整个旧分支强行覆盖到远端：

```bash
git cherry-pick 8e4c0f9
git cherry-pick 25d221a
```

如发生冲突：

```bash
git status
# 打开冲突文件，保留需要的双方内容并删除冲突标记
git add <resolved-file>
git cherry-pick --continue
```

如果发现选错提交，可在尚未推送时安全取消本次挑选：

```bash
git cherry-pick --abort
```

## 4. 推送独立分支并创建 PR

```bash
git diff --check origin/main...HEAD
git status --short
git push -u origin docs/roscar-uwb-plan
gh pr create --base main --head docs/roscar-uwb-plan
```

创建 PR 后，在 GitHub 的 **Files changed** 页面确认只包含计划内文件。若 GitHub 显示冲突，先把远端默认分支合入工作分支并在本地解决：

```bash
git fetch origin
git merge origin/main
# 解决冲突后执行 git add 和 git commit
git push
```

不要为了消除 PR 冲突而对共享分支使用 `git push --force`。

## 5. 本项目的文件边界

- 研究说明和计划放在 `docs/`。
- 引用条目集中放在 `references.bib`。
- 演示文稿、背景和预览放在 `ppt_month_plan/`。
- 后续 ROS 包放入单独工作空间或明确命名的包目录，不修改厂商驱动的历史；需要修改第三方代码时优先 fork 或记录固定 commit。
- rosbag、数据集、构建目录和缓存不提交 Git；只提交下载说明、校验和、参数及复现实验脚本。

这种目录隔离不能替代 Git 冲突检查，但能显著降低不同同学同时修改同一文件的概率。

