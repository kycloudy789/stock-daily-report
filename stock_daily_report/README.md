# 每日股市与基金简报

在 A 股每个交易日 14:05 自动采集 A 股主要指数、主要板块、场内 ETF 与全球主要股市（美股、韩股、日经、恒指等），结合最近几个交易日与近一月走势生成中文简报，并把网页链接通过微信推送，点击链接即可在微信内直接查看，无需下载。

## 功能

- 交易日判断：内置周末与 2026 年法定节假日，非交易日自动跳过。
- 多数据源：东方财富为主源，腾讯、新浪、Naver 为备用源，单类数据失败时自动回退。
- 市场概览：汇总两市成交额、涨跌家数与涨跌停数量，并按量能区间与涨跌家数给出客观情绪评价，附 A 股主要指数。
- 昨日收盘：各指数、板块、外盘与 ETF 表格均新增“昨日收盘”列，优先用行情接口昨收，缺失时反推。
- 走势图：表格中指数、板块、外盘、ETF 名称可点开展开近一周/近一月收盘价折线图。
- 重点指数观察：覆盖中证 A500、白酒、医疗、证券、银行、保险、中药、家电、新能源车、光伏、电网设备、恒生科技等基金相关指数。
- 重点科技与医药方向：单独展示 AI 应用、人工智能、算力、光模块、通信、半导体、芯片、软件、机器人，以及创新药、医药、医疗、生物医药等方向的当日表现。
- 板块与观点：提供领涨/领跌行业、重点关注行业、热门概念，并生成板块观点与今日观点。
- 基金视角：除 A 股指数与板块外，同时整理常见 ETF 行情；结合重点方向与近一周/近一月走势，给出“今日基金标的参考”（具体场内 ETF 与理由），并按量价关系生成规则化操作建议。
- 外围市场：覆盖美股（道指、纳指、标普）、韩股、日经、恒指、台湾、英德及越南胡志明等，辅助判断全球风险偏好。
- 微信推送：PushPlus HTML 消息，正文优先发送整份报告，微信内即可阅读；正文超过单条容量上限时自动降级为“链接+摘要”，点击链接在微信内置浏览器打开网页版，不需要下载文件。
- 建议来源：配置 AI 分析师 API Key 后，基金标的与操作建议由 AI 分析师基于当日行情即时生成；未配置或调用失败时自动降级为系统规则方案，并在文档中标注实际来源。
- 网页发布：支持 GitHub Pages 或本地目录，生成手机友好的单页 HTML。

## 配置

复制 `config.example.json` 为 `config.json`（项目内已创建），填写以下字段：

| 字段 | 说明 |
| --- | --- |
| `PushPlus Token` | PushPlus 微信推送令牌，也可用环境变量 `PUSHPLUS_TOKEN`；云端运行时应存为 GitHub Actions Secret |
| `PushPlus 群组编码` | 推送到群组时填写，个人微信留空 |
| `GitHub仓库` | GitHub 仓库名，如 `你的用户名/stock-daily-report` |
| `发布方式` | `github` 或 `local`，本地测试建议先使用 `local` |
| `AI 分析师 API Key` | AI 分析师接口密钥（如 DeepSeek Key），也可用环境变量 `AI_ANALYST_API_KEY`；不填则使用系统规则备用方案 |
| `AI 分析师 API地址` | 任意 OpenAI 兼容接口地址，默认 `https://api.deepseek.com`，环境变量 `AI_ANALYST_BASE_URL` |
| `AI 分析师模型` | 接口模型名，默认 `deepseek-chat`（如 Qwen、GPT 等兼容模型均可），环境变量 `AI_ANALYST_MODEL` |

发布到 GitHub Pages 前需要先登录：`gh auth login`。

## AI 分析师

投资建议不再由程序规则直接生成：采集完成后会把当日指数、重点科技与医药方向、板块、外盘、场内 ETF 与近一周/近一月走势整理成数据文本，调用 OpenAI 兼容接口让大模型担任分析角色，输出“基金操作建议”“今日基金标的参考”“今日观点”“风险提示”。

实现上参考了开源金融大模型项目的通行做法（如 AI4Finance-Foundation/FinGPT、FinRobot 等，均采用 LLM 接口 + 行情数据的组合），本项目保持轻量：只调用公开行情接口 + 标准 `/chat/completions`，不引入重型训练依赖。基金参考会与真实 ETF 名称/代码做核对，防止模型输出不存在标的。

云端启用方式（使用 DeepSeek，成本按 token 计费，每天一条简报、月成本约几元）：

```powershell
gh secret set AI_ANALYST_API_KEY --repo kycloudy789/stock-daily-report
```

也可在 GitHub 仓库 Settings -> Secrets and variables -> Actions 添加 `AI_ANALYST_API_KEY`（必填）、`AI_ANALYST_BASE_URL`、`AI_ANALYST_MODEL`（可留空用默认值）。不配置时流程照常运行，但会退回系统规则备用方案，简报中会明确标注。

## 本地运行

```powershell
cd D:\codex\工作流\stock_daily_report
python -B run_daily.py --dry-run --date 2026-08-14
python -B run_daily.py --offline --dry-run
```

参数说明：

- `--dry-run`：只生成文档，不发布、不推送。
- `--offline`：使用样例数据，不访问网络。
- `--force`：非交易日也强制生成。
- `--publish local`：只发布到本地 `site` 目录。
- `--collect-after HH:MM`：北京时间，早于该时刻则等待后再采集行情（默认不等待）。
- `--push-after HH:MM`：北京时间，早于该时刻则等待后再推送微信（默认不等待）。

## 云端自动运行（无需电脑开机）

项目内置 GitHub Actions 定时工作流 `.github/workflows/daily_report.yml`，周一至周五在 GitHub 云端自动执行：

1. 采集 A 股指数、主要板块、ETF 与全球市场数据。
2. 判断当天是否 A 股交易日，非交易日自动结束。
3. 生成 `docs/index.html` 与 `docs/report.md`，自动提交并发布 GitHub Pages。
4. 通过 PushPlus 把整份 HTML 报告推送到个人微信。

配置一次即可长期运行，电脑可以关机或睡眠。首次配置：

```powershell
# 把 PushPlus Token 存入仓库 Secret，Token 不会出现在代码里
gh secret set PUSHPLUS_TOKEN --repo kycloudy789/stock-daily-report
```

也可以手动到 GitHub 仓库的 Settings -> Secrets and variables -> Actions 添加 `PUSHPLUS_TOKEN`。需要手动测试一次时，在 Actions 页面点击 `每日股市与基金简报` 的 `Run workflow` 即可。

注意：GitHub Actions 的定时任务在仓库超过 60 天没有任何活动时会自动暂停；本项目每天自动提交报告，因此不会被暂停。

关于 14:05 送达：GitHub 的 `schedule` 定时任务存在排队延迟且时间不可控。本项目采用双层时间锁定：工作流在北京时间 13:25（UTC 05:25）触发以留出排队缓冲，脚本内再锁两个时刻——13:45 后才开始采集行情，14:00 整再推送微信，把送达时间收窄到 14:00-14:05。只要 Actions 在 14:00 前开始运行，微信送达基本稳定在这五分钟内，不再受 40 分钟级排队延迟影响。

## 本地备用运行

本地仍可用 Codex 自动化或手动命令运行，适合调试与排查：

```powershell
python -B run_daily.py --offline --dry-run
python -B run_daily.py
```

## 数据源与免责声明

行情来自东方财富、腾讯、新浪财经与 Naver 公开接口，接口字段可能变化，简报会标注实际使用的数据源。内容仅供信息参考，不构成投资建议。
