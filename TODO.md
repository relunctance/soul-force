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

#### 3. L5 ⇄ L0 双向闭环（反馈回路）

**目标**：L5 进化结果写回 L0（hawk-bridge），影响未来 recall

**实现方式**：
- 成功修复 → 写回 hawk-bridge，高 importance（fix）
- 失败修复 → 写回 hawk-bridge，标记为 low importance + 来源=verify-failure

```python
def write_back_to_hawkbridge(result):
    if result['type'] == 'success':
        hawk_bridge.add_memory(
            text=f"[ISSUE-{result['issue_id']}] 修复成功: {result['pattern']}",
            category='decision',
            importance=0.9,  # 高优先级
            source='auto-evolve-verify',
            metadata={'issue_id': result['issue_id']}
        )
    else:
        hawk_bridge.add_memory(
            text=f"[ISSUE-{result['issue_id']}] 修复失败: {result['pattern']}",
            category='other',
            importance=0.3,  # 低优先级
            source='auto-evolve-verify',
            metadata={'issue_id': result['issue_id'], 'failure': True}
        )
```

**效果**：
- 下次 hawk recall 时，成功模式会优先被注入上下文
- 失败模式会被降权，避免重蹈覆辙

---

#### 4. 向 L6 qujin-editor 写进化建议

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

#### 5. 读 L1 inspect 报告（首次巡检结果）

**目标**：L5 也应读取 L1 的首次巡检结果，作为进化的上下文输入

**原因**：验证结果（solved/unsolved）需要结合首次巡检的问题描述，才能提炼完整模式

```python
def read_inspect_report(run_id):
    """读取首次巡检报告，作为进化上下文"""
    path = f"~/.hawk/inspect-reports/{run_id}.json"
    with open(path) as f:
        return json.load(f)
```

---

#### 6. 进化事件知识库

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
Step 1: read_verify_report()        ← 读取 auto-evolve verify 输出
Step 2: read_inspect_report()       ← 读取 L1 首次巡检报告（完整上下文）
Step 3: write_success_pattern()      ← 成功模式写入 SOUL/USER
Step 4: write_failure_trap()        ← 失败模式写入 MEMORY（坑）
Step 5: write_back_to_hawkbridge()   ← L5 → L0 写回反馈回路
Step 6: evolution-log.jsonl          ← 进化事件知识库
Step 7: 向 qujin-editor 写建议       ← L5 → L6 反馈
Step 8: 自动触发机制                 ← cron/webhook/file_watch
Step 9: 进化效果追踪                 ← metrics.json
```

---

## 参考架构

```
L0 记忆层（hawk-bridge）
    ↓ 上下文触发
L1 巡检层（auto-evolve inspect）
    ↓ 输出 inspect-reports/{run_id}.json
L4 验证层（auto-evolve verify）
    ↓ 输出 verify-reports/{run_id}.json
L5 进化层（soul-force）
    ← 读取 L1 inspect 报告（问题上下文）
    ← 读取 L4 verify 报告（验证结果）
    ↓ 成功 → SOUL.md / 失败 → MEMORY.md（坑）
    ↓ 同时 → evolution-suggestions.json（向 L6 写建议）
    ↓ 记录 → evolution-log.jsonl（进化知识库）
    ↓ 反馈 → hawk-bridge 写回（成功高优/失败低优）
L6 知识层（qujin-editor）
    ← 读取 evolution-suggestions.json
    ↓ 决定是否修订宪法
```

**关键：L5 ⇄ L0 双向闭环**
- L5 成功/失败结果写回 hawk-bridge
- hawk-bridge 的 recall 感知进化结果，影响未来注入的记忆优先级

---

## 更深层能力补全（v2.4+）

### L. 模式冲突检测

**目标**：新模式和 SOUL 中现有模式矛盾时，触发 review 而不是直接覆盖

**检测逻辑**：
- 新模式与现有模式关键词重叠 > 80%
- 但结论相反（如"永远不要用 jQuery" vs "可以用 jQuery"）

**处理流程**：
1. 检测到矛盾 → 写入 `soulforge.conflicts`
2. 触发 review → 用户确认保留哪个
3. 或者 SoulForce 自己判断（根据验证次数多的优先）

---

### M. 回滚到指定版本

**当前**：`rollback()` 只回滚到上一个快照

**升级**：
- 按时间戳回滚：`rollback --file SOUL.md --at "2026-04-01"`
- 查看版本列表：`soulforge log --file SOUL.md`
- 对比任意两版本：`soulforge diff --file SOUL.md --v1 1 --v2 3`

---

### N. 进化路径可视化

**目标**：看到模式是怎么一步步进化成现在的

**命令**：`soulforge changelog --visual`

**输出示例**：
```
SOUL.md 进化路径
│
├── v1 (2026-01-01)
│   └── 初始版本
│
├── v2 (2026-02-15)  ← 第二次进化
│   └── +偏好: 用户喜欢 Arial
│       +反馈: 不要用 jQuery
│
└── v3 (2026-04-12)  ← 当前
    └── +事实: 用户是产品经理
        +修正: jQuery → 原生 JS（override v2 冲突）
```

---

### O. 进化质量评分

**目标**：量化进化质量，防止退化

**评分维度**：
| 维度 | 说明 | 计算 |
|------|------|------|
| 覆盖度 | SOUL 覆盖了多少个工作场景 | 已有模式数 / 可能场景数 |
| 一致性 | 模式之间是否矛盾 | 冲突对数 / 总模式对数 |
| 可执行性 | 模式是否具体可操作 | 模糊描述数 / 总模式数 |

**每次进化后输出**：
```
进化质量评分：
- 覆盖度: 0.75 (↑ +0.05)
- 一致性: 0.90 (— 无变化)
- 可执行性: 0.80 (↓ -0.10) ← 注意退化
警告: 可执行性下降，v3 引入了模糊描述
```

---

### P. 增量进化（已部分实现）

**目标**：只分析新增记忆，不需要全量分析

**当前**：`last_run` timestamp 已实现增量分析

**升级**：
- 增量分析支持按 issue 粒度
- 支持 `soulforge run --since "2026-04-01"` 指定时间段
- 支持 `soulforge run --issues ISSUE-001 ISSUE-002` 只分析特定 issue

---

### Q. SOUL 自我诊断

**目标**：不依赖外部，SOUL 自己检测自己是否过时

**功能**：
- 定期扫描 SOUL 中的模式
- 检查哪些模式对应的记忆已被验证为"错误"
- 自动降级或删除过时模式

**触发条件**：
- soul-force 写入了 `evolution-failure` 记忆
- 该记忆关联的模式在 SOUL 中存在
- 自动降级该模式为"已废弃"

---

## 细粒度补充（v2.5+）

### R. Team SOUL（团队共享学习）

**目标**：多 Agent 的学习成果汇入"团队 SOUL"

**实现**：
- `soulforge team-sync` — 把 personal SOUL 中的 team-visible 模式同步到团队共享区
- 团队共享区供所有 Agent 读取，但只有唐僧可写

---

### S. SOUL 模板生成

**目标**：新 Agent 启动时，SoulForce 自动生成基础模板

**实现**：
- `soulforge init --template developer` — 生成开发者角色模板
- `soulforge init --template pm` — 生成产品经理模板
- 基于 project-standard 的角色描述自动生成

---

### T. Evolution Rollback Queue

**目标**：一次进化失败时，批量回滚所有改动

**实现**：
```bash
soulforge rollback --all  # 回滚上次所有改动
soulforge rollback --last 3  # 回滚最近 3 次进化
```

---

### U. Pattern Schema 验证

**目标**：写入前验证格式，避免畸形 pattern 污染 SOUL

**验证规则**：
- 必须有 `timestamp`
- 必须有 `pattern` 字段
- `tags` 必须是数组
- `confidence` 必须在 0-1 范围

---

### V. SOUL 健康仪表盘

**目标**：覆盖率/冲突率/平均寿命 综合打分

**命令**：`soulforge health`

**输出**：
```
SOUL 健康报告：
- 覆盖率: 0.75 (75% 工作场景有模式覆盖)
- 冲突率: 0.05 (5% 模式对存在矛盾)
- 平均寿命: 42 天 (模式从创建到废弃的平均时长)
- 进化速度: 3.2 次/月
综合评分: 82/100 ✓
```

---

## 多租户支持（v2.6+）

### MT-1. per-tenant SOUL/USER/IDENTITY

**目标**：每个租户有独立的身份文件

```
~/.soul-force/
  tenants/
    {tenant_id}/
      SOUL.md
      USER.md
      IDENTITY.md
      evolution-log.jsonl
      evolution-suggestions.json
```

---

### MT-2. Global Learnings 共享

**目标**：厂商维护的 Global learnings 所有租户共享

```python
# 读取优先级
def load_learnings(tenant_id):
    global_path = "~/.soul-force/global/learnings.jsonl"
    tenant_path = f"~/.soul-force/tenants/{tenant_id}/learnings.jsonl"
    # 合并：租户私有 + Global（租户只读 Global）
```

---

### MT-3. tenant_id 隔离审核

**目标**：qujin-editor 审核时按 tenant_id 隔离

- 只有 tenant_id 匹配才能审核该租户的进化建议
- Global constitution 修订需要厂商权限
