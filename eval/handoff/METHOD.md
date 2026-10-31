# 方法及关键代码

## 追链方法（九行）

1. 从冻结合成交易中选择符合类型与金额条件的候选边。
2. 按规则版本读取时间窗，v1 为 60 分钟，v2 为 120 分钟。
3. 两笔交易付款收款衔接、时间递增且在窗口内才可能链接。
4. 同时检查上游和下游资金守恒条件。
5. 构建交易链接图，弱连通分量作为候选链。
6. 检查链上至少一笔达到规则的链金额门槛。
7. 角色从图的出入关系计算，不能把账户集合当作连续路径。
8. max_hops 仅裁剪返回边；完整统计仍描述原链，需保留 truncated。
9. 链与规则命中结合生成辅助工单，正常业务反证不能遗漏。

## 追链（core/trace.py）

```python
longest = {}
for e in reversed(es):
    longest[e["tx_id"]] = 1 + max(
        (longest[y] for y in succ[e["tx_id"]]), default=0)
sources = [e for e in es if not pred[e["tx_id"]]]
```

链接严格按时间递增，倒序计算最长路径。sources 可能有多个，表示并行汇入，不能串成付款路径。链总金额只统计源交易，不能把每一跳累加当作受骗本金。

## 规则命中（core/rules.py）

```python
for r in active_rules(rs):
    fn = IMPLS.get(r["impl"])
    if fn is None:
        raise ValueError("Unsupported rule implementation")
    res = fn(c, r)
    if res is None:
        continue
    ev, detail, metrics = res
```

这是原函数关键结构的摘录，异常文字作了缩写。YAML 指定条件与参数，impl 分发到具体算法；风险与反向规则分别保留，最终状态由 ticket.judge 决定。

## 重判（core/rejudge.py）

```python
for a in sorted(st.accounts):
    jo, jn = judge(st, a, old_v), judge(st, a, new_v)
    if jo["status"] == jn["status"]:
        continue
    ro, rn = set(jo["H"] + jo["K"]), set(jn["H"] + jn["K"])
    added = sorted(rn - ro, key=rule_sort_key)
    removed = sorted(ro - rn, key=rule_sort_key)
```

同一冻结数据分别按两个规则版本判定，只列状态变化。8 户变化是规则口径变化，不是账户行为在两个时刻变化。
