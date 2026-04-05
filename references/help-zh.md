# SoulForge - AI 智能体记忆进化系统

自动分析记忆文件，发现行为模式，进化你的 AI 身份文件。

## 使用方式

    soulforge.py run [--workspace PATH] [--dry-run] [--force]
    soulforge.py status [--workspace PATH]
    soulforge.py diff [--workspace PATH]
    soulforge.py stats [--workspace PATH]
    soulforge.py inspect FILE [--workspace PATH]
    soulforge.py restore [FILE] [--backup PATH] [--preview] [--all]
    soulforge.py reset [--workspace PATH]
    soulforge.py template [TEMPLATE]
    soulforge.py changelog [--zh] [--full] [--visual]
    soulforge.py cron [--every MINUTES]
    soulforge.py cron-set [--every N] [--show] [--remove]
    soulforge.py review [--workspace PATH] [--tag TAG] [--confidence LEVEL] [--interactive]
    soulforge.py apply [--confirm] [--workspace PATH] [--interactive]
    soulforge.py backup --create [--workspace PATH]
    soulforge.py ask "question" [--workspace PATH]
    soulforge.py help

## 示例

    soulforge.py run                    # 运行进化（带自动回滚）
    soulforge.py run --dry-run        # 预览模式（显示 unified diff，不写入）
    soulforge.py run --force           # 强制应用所有模式（忽略置信度）
    soulforge.py run --notify         # 运行并发送飞书通知
    soulforge.py review                # 审查模式：生成模式但不写入
    soulforge.py review --tag preference # 按标签过滤模式
    soulforge.py review --confidence high --tag error  # 组合过滤
    soulforge.py review --interactive   # 交互式审查：逐个确认
    soulforge.py apply --confirm        # 从 review 结果确认后写入
    soulforge.py apply --interactive   # 从交互式审查结果应用
    soulforge.py backup --create       # 创建手动快照
    soulforge.py status               # 查看当前状态（含 token 预算）
    soulforge.py clean --expired      # 清除过期模式块
    soulforge.py clean --expired --dry-run  # 预览过期块（不实际删除）
    soulforge.py rollback --auto      # 显示回滚自动化信息
    soulforge.py config --show        # 显示当前配置
    soulforge.py config --set max_token_budget=8192  # 设置配置
    soulforge.py changelog --zh        # 查看中文更新日志
    soulforge.py changelog --visual   # 以 ASCII tree 形式查看更新日志
    soulforge.py ask "我的沟通风格是什么？"  # 自然语言查询

---

## 命令说明

### run
运行进化过程。读取 memory/ 和 .learnings/ 中的记忆，
调用 LLM 分析模式，将发现的模式写入 SOUL.md、USER.md 等文件。

- `--dry-run`: 预览模式，只显示结果不写入文件
- `--force`: 强制应用所有模式（忽略置信度阈值）

### review
审查模式：生成模式分析结果但不写入文件。
输出所有待应用的模式，支持 JSON 格式导出。
结果保存到 `.soulforge-{agent}/review/latest.json`。

- `--tag TAG`: 按标签过滤模式 (v2.2.0)
- `--confidence LEVEL`: 按置信度过滤：high, medium, low (v2.2.0)
- `--interactive`: 交互式审查：逐个询问是否应用 (v2.2.0)

### apply
从 review 结果确认后写入。需要先运行 `soulforge.py review`。
- `--confirm`: 确认应用所有审查过的模式
- `--interactive`: 从交互式审查决策文件应用 (v2.2.0)

### backup
备份管理：
- `--create`: 创建手动快照（区别于自动备份）

### status
显示当前状态概览。包括：记忆条目数量、各源文件统计、目标文件状态、备份文件数量。

### diff
显示上次运行以来的变化。对比当前文件与最新备份的差异。

### stats
显示进化统计。包括：SoulForge 更新次数、各文件进化次数、备份文件统计。

### inspect FILE
检查特定文件（如 SOUL.md）的进化模式。
显示当前内容以及发现的待应用模式。

### restore [FILE] [--backup N] [--preview] [--all]
从备份恢复文件。
- 不带参数：列出所有可用备份
- `--backup N`: 指定第 N 个备份恢复（1=最新）
- `--preview`: 预览变更内容，不实际恢复
- `--all`: 恢复所有有备份的文件

### reset
重置 SoulForge 状态。删除所有备份和状态文件。
注意：不会修改目标文件（SOUL.md 等）。

### template [NAME]
生成目标文件的标准模板。
- 不带参数：列出所有可用模板
- 带参数：显示指定模板内容

### changelog [--zh] [--full] [--visual]
显示进化日志。
- `--zh`: 显示中文版本（默认）
- `--full`: 显示完整日志（不截断）
- `--visual`: 以 ASCII tree 可视化形式显示 (v2.2.0)

### ask "question"
用自然语言查询智能体的身份/记忆 (v2.2.0)。
从已有 patterns 和 memories 合成答案，不写入任何文件，不会触发分析。

示例：
    soulforge.py ask "我的沟通风格是什么？"
    soulforge.py ask "代码审查有什么偏好？"

### cron [--every MINUTES]
显示定时任务设置帮助。

### cron-set [--every N] [--show] [--remove]
通过 OpenClaw 设置定时任务。
- `--every N`: 设置为每 N 分钟运行一次
- `--show`: 显示当前定时任务
- `--remove`: 删除定时任务

### help
显示帮助信息。

---

## 全局参数

- `--workspace PATH`: 指定工作区目录。默认: ~/.openclaw/workspace
- `--config PATH`: 指定配置文件路径。
- `--dry-run`: 预览模式，只显示结果不写入文件。
- `--force`: 强制应用所有模式（忽略置信度阈值）。
- `--log-level LEVEL`: 日志级别: DEBUG, INFO, WARNING, ERROR

---

### clean --expired [--dry-run]
清除目标文件中过期的 SoulForge 更新块。

- `--expired`: 必填标志，确认执行此操作
- `--dry-run`: 预览将要清除的内容，不实际删除

过期块是指包含 `**Expires**: YYYY-MM-DD` 且日期已过的块。

### rollback --auto
显示回滚自动化信息。回滚在 `run` 期间自动应用，此命令用于显示状态。

### config --show | --set KEY=VALUE
显示或设置配置值。值会持久化到 `~/.soulforgerc.json`。

示例：
```
soulforge.py config --show
soulforge.py config --set max_token_budget=8192
soulforge.py config --set notify_on_complete=true
soulforge.py config --set notify_chat_id=oc_xxx
soulforge.py config --set rollback_auto_enabled=false
```

## 置信度分级

- 高置信度 (>0.8): 自动应用
- 中置信度 (0.5-0.8): 需要 review 后确认
- 低置信度 (<0.5): 忽略，不生成模式

---

## 增量分析

首次运行会分析全部历史记忆。之后只分析自上次运行以来的新条目，
通过 `.soulforge-{agent}/last_run` 文件记录时间戳。

---

更多信息:
  https://github.com/relunctance/soul-force
