# 文章审阅：292 / 312 叙事的证据边界

本文档把文章中的说法拆成可审计的 claim。它不把文章里的“观察到”自动升级为公开协议事实，也不提供绕过服务端调度的实现。

## Claim / evidence matrix

| 主题 | 证据级别 | 本仓库的安全处理 |
| --- | --- | --- |
| fixture 中出现数字状态 `292` 或 `312` | `observed_fixture` | 只记录数字和字段存在性。 |
| `292` 携带名为 `current_turn_state` 的字段 | `observed_fixture`（仅限给定 fixture） | 将值视为不透明敏感字段；不解释用途。 |
| `292` 是通行证、`312` 是降智/撤销信号 | `unknown` / `hypothesis` | 没有原始协议、对照实验或官方定义，程序不推断。 |
| TTL 约一小时、换 IP 仍有效、特定模型/IP 能稳定签发 | `unverified` | 只对 fixture 的时间戳做本地算术；不切换网络、不发请求。 |
| 代理注入、状态续期、账号凭据或服务端调度绕过 | `unsafe_do_not_implement` | 不提供代码、配置、抓包步骤或操作指南。 |

## 工具如何对应文章

- `validation.py`：严格读取本地 JSON，记录状态码、字段存在性和时间字段；`292/312` 始终为 `unknown`。
- `redaction.py`：确定性脱敏常见 token/cookie/API key 形态，报告只保留路径和摘要；命令行发现疑似凭据时 fail-closed。
- `simulation.py`：用整数 TTL 模拟 `unknown → observed → expired/revoked`，撤销只能由显式本地事件触发。
- `reporting.py`：生成 JSON/Markdown 证据报告，不连接在线服务。

## 不能从本仓库推出的结论

本地测试通过不代表任何在线服务会返回某个状态码、签发某个字段、保持某个有效期，或改变模型质量。它也不验证账号资格、IP 关系、套餐权益或服务条款。

文章中的联系方式、第三方仓库/个人信息、真实凭据和任何要求代理拦截、状态注入、出口切换或重放请求的内容都没有复制进仓库。
