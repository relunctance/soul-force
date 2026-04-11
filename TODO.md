# SoulForce v2.3 Roadmap — 自我进化架构 L5 层补全

## 背景

SoulForce 是自我进化闭环 L5 层（进化层）的核心组件。当前功能与 L5 需求的差距见下方。

---

## 当前能力 vs L5 需求差距

| 能力 | 当前 | 架构需求 | 状态 |
|------|------|----------|------|
| 读取记忆 | ✅ hawk-bridge | ✅ | 完成 |
| 模式分析（LLM） | ✅ | ✅ | 完成 |
| 写入 SOUL/USER/IDENTITY | ✅ | ✅ | 完成 |
| 记录"坑"（失败模式） | ❌ | ✅ | **待实现** |
| 读 L4 验证报告 | ❌ | ✅ | **待实现** |
| 区分成功/失败写入 | ❌ | ✅ | **待实现** |
| 向 L6 写进化建议 | ❌ | ✅ | **待实现** |
| 自我纠正（进化闭环） | ❌ | ✅ | **待实现** |

---

## 待实现功能

### P0 — 核心闭环功能

#### 1. 读 L4 验证报告（auto-evolve verify）

**目标**：订阅 auto-evolve verify mode 的输出，获取修复结果

**实现方式**：
- auto-evolve verify 输出 JSON 报告到 `~/.hawk/verify-reports/{run_id}.json`
- soul-force 读取最新报告，解析每个问题的状态：`solved` / `unsolved`

**验证报告格式（auto-evolve 输出）**：
```json
{
  "run_id": "verify_20260412",
  "baseline_run_id": "inspect_20260411",
  "timestamp": "2026-04-12T00:00:00Z",
  "results": [
    {
      "issue_id": "ISSUE-001",
      "description": "未使用 DTO 类型",
      "status": "solved",
      "evidence": "DTO 已在 Logic 层使用"
    },
    {
      "issue_id": "ISSUE-002",
      "description": "事务未包裹写操作",
      "status": "unsolved",
      "evidence": "仍有 2 处写操作未包裹"
    }
  ]
}
```

**文件路径**：`scripts/soulforge.py` 新增 `read_verify_report()` 函数

---

#### 2. 区分成功/失败模式写入

**目标**：成功和失败用不同策略写

**成功修复**：
- 提炼成功模式 → 写入 `SOUL.md` / `USER.md`
- 格式：
  ```
  ## 成功模式
  - [2026-04-12] {场景描述}
    方法：{修复方法}
    来源：auto-evolve verify #ISSUE-001
  ```

**失败修复**：
- 记录为"坑" → 写入 `MEMORY.md`
- 格式：
  ```
  ## 避坑记录
  - [2026-04-12] {场景描述}
    失败方法：{尝试过的方法}
    失败原因：{失败原因}
    不要重蹈：{避免方式}
    来源：auto-evolve verify #ISSUE-002
  ```

**文件路径**：`scripts/soulforge.py` 新增 `write_success_pattern()` + `write_failure_trap()` 函数

---

### P1 — 进化生态对接

#### 3. 向 L6 qujin-editor 写进化建议

**目标**：当某类问题反复出现时，建议修订宪法

**触发条件**：同一 issue_id 或同类问题出现 3 次以上仍未解决

**输出格式**（`~/.soul-force/evolution-suggestions.json`）：
```json
{
  "suggestions": [
    {
      "type": "constitution_update",
      "issue": "事务写操作规范缺失",
      "evidence": "3 次 verify 均发现同类问题",
      "suggestion": "建议在 qujin-constitution 新增「事务写操作检查清单」",
      "priority": "high"
    },
    {
      "type": "standard_addition",
      "issue": "DTO 使用规范不明确",
      "evidence": "ISSUE-001/003/007 均与 DTO 相关",
      "suggestion": "建议在 project-standard 新增 DTO 使用场景定义",
      "priority": "medium"
    }
  ]
}
```

---

#### 4. 进化事件知识库

**目标**：记录每次进化的事件，供后续参考

**存储位置**：`~/.soul-force/evolution-log.jsonl`

**格式**：
```jsonl
{"timestamp": "2026-04-12T00:00:00Z", "type": "success", "issue_id": "ISSUE-001", "pattern": "...", "context": "...", "result": "solved", "source": "verify"}
{"timestamp": "2026-04-12T00:01:00Z", "type": "failure", "issue_id": "ISSUE-002", "pattern": "...", "context": "...", "result": "unsolved", "source": "verify"}
{"timestamp": "2026-04-12T00:02:00Z", "type": "constitution_suggestion", "suggestion": "...", "priority": "high"}
```

**用途**：
- 追踪进化效果（问题是否越来越少）
- 分析失败模式规律
- 为后续 L5 → L6 反馈提供数据

---

### P2 — 自动化

#### 5. 自动触发机制

**目标**：L4 verify 完成后自动触发 L5 soul-force

**触发方式**：
- **cron**：每 6 小时跑一次，检查新 verify 报告
- **webhook**：auto-evolve verify 完成后调用 soul-force hook
- **文件监听**：监控 `~/.hawk/verify-reports/` 新增文件

**配置项**（`~/.soulforgerc.json`）：
```json
{
  "auto_evolve": {
    "enabled": true,
    "trigger": "cron",  // "cron" | "webhook" | "file_watch"
    "interval_hours": 6,
    "verify_reports_dir": "~/.hawk/verify-reports"
  }
}
```

---

#### 6. 进化效果追踪

**目标**：量化进化效果，判断系统是否在变好

**指标**：
- `issues_solved_rate` = 解决的问题数 / 总问题数
- `failure_pattern_count` = 失败模式累计数
- `constitution_updates` = 宪法修订次数
- `avg_fix_time` = 从发现到解决的平均时间

**输出**：生成 `~/.soul-force/evolution-metrics.json`
```json
{
  "period": "2026-04",
  "issues_solved_rate": 0.85,
  "total_issues": 20,
  "solved": 17,
  "unsolved": 3,
  "failure_pattern_count": 3,
  "constitution_updates": 2,
  "avg_fix_time_hours": 4.2
}
```

---

## 实现顺序建议

```
Step 1: read_verify_report()        ← 读取 auto-evolve 输出
Step 2: write_success_pattern()      ← 成功模式写入
Step 3: write_failure_trap()         ← 失败模式写入（坑）
Step 4: evolution-log.jsonl          ← 进化事件知识库
Step 5: 向 qujin-editor 写建议       ← L5 → L6 反馈
Step 6: 自动触发机制                 ← cron/webhook/file_watch
Step 7: 进化效果追踪                 ← metrics.json
```

---

## 参考架构

```
L4 验证层（auto-evolve verify）
    ↓ 输出 verify-reports/{run_id}.json
L5 进化层（soul-force）
    ↓ 读取报告
    ↓ 成功 → SOUL.md / 失败 → MEMORY.md（坑）
    ↓ 同时 → evolution-suggestions.json（向 L6 写建议）
    ↓ 记录 → evolution-log.jsonl（进化知识库）
L6 知识层（qujin-editor）
    ↓ 读取 evolution-suggestions.json
    ↓ 决定是否修订宪法
```
