# 每日股市与基金简报

在 A 股每个交易日 14:00 自动采集 A 股主要指数、主要板块、场内 ETF 与全球主要股市（美股、韩股、日经、恒指等），结合最近几个交易日生成中文简报，并把网页链接通过微信推送，点击链接即可在微信内直接查看，无需下载。

## 功能

- 交易日判断：内置周末与 2026 年法定节假日，非交易日自动跳过。
- 多数据源：东方财富为主源，腾讯、新浪、Naver 为备用源，单类数据失败时自动回退。
- 市场概览：汇总两市成交额、涨跌家数与涨跌停数量，并附 A 股主要指数。
- 重点指数观察：覆盖中证 A500、白酒、医疗、证券、银行、保险、中药、家电、新能源车、光伏、电网设备、恒生科技等基金相关指数。
- 板块与观点：提供领涨/领跌行业、重点关注行业、热门概念，并生成板块观点与今日观点。
- 基金视角：除 A 股指数与板块外，同时整理常见 ETF 行情，并结合近 5 个交易日生成规则化操作建议。
- 外围市场：覆盖美股（道指、纳指、标普）、韩股、日经、恒指、台湾、英德及越南胡志明等，辅助判断全球风险偏好。
- 微信推送：PushPlus HTML 消息，正文直接发送整份报告，微信内打开 PushPlus H5 页面即可阅读，不依赖境外网站，也不需要下载文件。
- 网页发布：支持 GitHub Pages 或本地目录，生成手机友好的单页 HTML。

## 配置

复制 `config.example.json` 为 `config.json`（项目内已创建），填写以下字段：

| 字段 | 说明 |
| --- | --- |
| `PushPlus Token` | PushPlus 微信推送令牌，也可用环境变量 `PUSHPLUS_TOKEN`；云端运行时应存为 GitHub Actions Secret |
| `PushPlus 群组编码` | 推送到群组时填写，个人微信留空 |
| `GitHub仓库` | GitHub 仓库名，如 `你的用户名/stock-daily-report` |
| `发布方式` | `github` 或 `local`，本地测试建议先使用 `local` |

发布到 GitHub Pages 前需要先登录：`gh auth login`。

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

## 云端自动运行（无需电脑开机）

项目内置 GitHub Actions 定时工作流 `.github/workflows/daily_report.yml`，周一至周五 06:00 UTC（北京时间 14:00）在 GitHub 云端自动执行：

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

## 本地备用运行

本地仍可用 Codex 自动化或手动命令运行，适合调试与排查：

```powershell
python -B run_daily.py --offline --dry-run
python -B run_daily.py
```

## 数据源与免责声明

行情来自东方财富、腾讯、新浪财经与 Naver 公开接口，接口字段可能变化，简报会标注实际使用的数据源。内容仅供信息参考，不构成投资建议。
