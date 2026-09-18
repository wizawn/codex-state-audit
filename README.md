# Codex State Audit

一个**本地、离线、证据优先**的状态信号审计与模拟工具。它对应一篇讨论“292 / 312 / `current_turn_state`”的文章，但不把文章中的解释当成已证实的公开协议，也不实现任何绕过服务端调度的功能。

> 重要边界：本项目不会连接 ChatGPT/OpenAI，不会拦截代理流量，不会注入或续期状态，不会切换 IP/出口，不会读取账号凭据，也不会把 292/312 解释为“通行证”“降智”或其他官方语义。

## 能做什么

- 读取用户自备、已脱敏的 JSON fixture；
- 记录状态码、字段存在性和明确时间戳；
- 将 292、312 和 `current_turn_state` 当作不透明的观测标签；
- 对 token、cookie、Authorization、API key 等常见敏感形态做确定性脱敏；
- 生成 JSON / Markdown 证据报告；
- 在本地整数算术中模拟 TTL、过期和显式撤销。

所有“网络行为”都被刻意排除。通过测试只说明本地输入规则正确，不说明任何在线服务的内部实现、账号资格、模型质量或服务条款。

## 快速开始

需要 Python 3.11 或更高版本：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'

# 校验并输出 JSON 报告
codex-state-audit validate fixtures/observed-292.json

# 输出 Markdown 报告
codex-state-audit report fixtures/observed-312.json --format markdown

# 纯本地 TTL 模拟；label 只是 opaque 注释，不改变状态
codex-state-audit simulate --ttl-seconds 3600 --elapsed-seconds 120 --label 292

# 运行测试
pytest
```

命令行在发现疑似未脱敏凭据时会 fail-closed，返回退出码 `2`；它不会把原值写入报告。结构错误返回 `1`，成功返回 `0`。

## 输入格式

fixture 至少包含 `fixture_version`、`response.status_code`，可选 `captured_at`、`response.body.expires_at` 和 `claims`。建议把来源写成 `fixture-generated-redacted` 或 `user-supplied-redacted`，并在上传前自行确认没有真实秘密。

示例中的 `observed-292.json` / `observed-312.json` 只使用虚构值和明确的 `[REDACTED:…]` 占位符，不代表真实抓包。

## 原理与正误边界

文章审阅见 [`docs/article-review.md`](docs/article-review.md)。核心原则是：

1. “字段出现”不等于“字段含义已知”；
2. 两个时间戳的差值只是 fixture 算术，不等于服务器 TTL；
3. 状态机只接受显式的本地 `revoke` / `expire` 事件，绝不由 HTTP 数字自动触发；
4. 报告只输出路径、类别和短摘要，不输出原始敏感值。

## 不包含的内容

仓库没有私有端点调用、代理配置、TLS 绕过、越狱步骤、状态注入、账号切换、凭据采集、请求重放或出口切换代码。文章中的联系方式、二维码、第三方仓库和个人信息也没有复制。

## 许可证

MIT，见 [`LICENSE`](LICENSE)。
