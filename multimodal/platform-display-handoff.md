# Nexent 推理与执行轨迹隔离交接

## 已核实范围

2026-11-07 测试服务器页面自报 Nexent v2.7.0。普通问答既有多模态测试发布版与草稿调试页均可见 Reasoning；调试页还可见 Executed code。平台设置中未找到受支持的仅最终回答展示开关。关闭模型深度思考不能保证关闭 ReAct 的规划文本或工具执行记录，不将其当作隔离修复。

已只读检查公开上游 `https://github.com/nexent-hub/nexent` 的 v2.7.0 标签，提交 `519b9b17c7f4cbc623256ac318ea96a20f33772e`。服务器实际镜像是否与该提交完全相同尚未核对，不能直接套补丁。源码检索用于定位，不代表已修改或部署服务器。

## 源码定位

| 位置（上游仓库） | 观察 |
|---|---|
| frontend/app/[locale]/newchat/assistant-ui/thread.tsx，约 1440–1580 行 | reasoning、execution-code、tool-call 进入 chainOfThought 分组并渲染 |
| frontend/app/[locale]/newchat/ui/reasoning.tsx，约 137 行 | Reasoning 标题与内容组件 |
| frontend/app/[locale]/newchat/ui/execution-code-block.tsx，约 22–40 行 | 默认展开，显示 Executed code |
| frontend/app/[locale]/newchat/adapter/conversation-thread-list-adapter.tsx，约 357 行起 | 历史 thinking 恢复为 reasoning，不能只修实时流 |
| backend/management/services/agent/run.py，约 498–788 行 | 流事件序列化、持久化及发送；需同时检查恢复/重放路径 |
| backend/services/conversation_management_service.py，约 884–945 行 | 历史 message units 包含工具信息并返回 |
| sdk/nexent/core/utils/observer.py，约 39 行 | 定义 model_output_thinking、model_output_deep_thinking、model_output_code、parse、execution_logs、tool 等事件 |

行号只适用于上述上游提交。正式实施前先核对服务器镜像版本与源码提交。

## 修复要求

1. 在服务端以用户身份和权限决定可返回的事件，不信任客户端 is_debug 标记自行授权。普通问答只返回必要的最终答案、引用及运行状态；工具参数、原始结果、执行代码、内部规划与隐藏推理不发送到普通客户端。
2. 实时流、断线恢复/重放、历史详情、分享及导出执行同一投影策略，避免旧历史恢复泄露。
3. 调试权限与普通问答权限分离；调试记录按最小必要保留，不把详细模型推理当作默认交付内容。
4. 前端按获授权的数据渲染；不能仅折叠、CSS 隐藏或删除 DOM 后声称数据隔离完成。
5. 保留用户可读的证据编号、规则引用及必要计算结果，不以隐去内部轨迹为由丢失研判依据。

## 服务器部署验证

- 取得服务器可用 SSH/平台源码部署渠道后核对镜像与提交。当前 BatchMode SSH 返回 publickey/password 拒绝；未读取密码，未修改服务器。
- 普通问答分别测试无工具、图片、PDF、账户研判与工单生成。确认答案和引用完整，页面及网络响应不含内部推理/代码/工具参数。
- 刷新历史、切换会话、断线恢复、分享/导出分别验证；普通用户不能通过 is_debug=true 获得额外记录。
- 与管理员调试视图分别验收，完成后才解除多模态发布 HOLD。

此项当前是部署与平台改造阻塞，不是提示词可解决的问题；未发布未验收草稿。
