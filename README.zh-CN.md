# Paper Research Daily

**把研究目标变成一套可持续的论文阅读流程。** 用户选择课题，与 Agent 确定标准，再由 Agent 检索、核验、精读、评分和归档。Python 工具负责去重与文献库状态，所有成果默认保存在本地。

[English](README.md) · [Skill 入口](SKILL.md) · [筛选规则](references/selection.md) · [阅读卡片](references/reading-card.md)

适用于机器人、机器学习、生物学、社会科学等领域。不同课题可以选择自己的来源、证据标准和阅读目标，不需要沿用某个固定博士课题。

## 能做什么

- 首次使用时确认课题、研究问题、排除方向、每日数量、来源、评分、语言和时间设置。
- 默认每天 8 篇：工作日 4 篇新文＋4 篇正式发表，周末从备选与当天候选中综合选 Top 8；均可调整。
- 提供 arXiv 检索及最新列表、Crossref、OpenAlex 工具，由 Agent 核验正式发表状态、全文版本和来源。
- 按匹配度、证据、启发、创新、代表性、复现条件评分，保留备选、待核验和淘汰理由。
- 根据 DOI、去版本 arXiv ID、题名与作者、文件哈希跨日期、跨版本去重，现有 PDF 也纳入排重。
- 输出高密度阅读卡片：摘要转述、方法、创新、证据表、局限、研究用途和可验证的下一步。
- 下载可用 PDF，维护日期文件夹、结构化元数据、日志、总索引和历史；预备阶段不占正式推荐名额。

这是 **Agent 工作流＋确定性工具**。Python CLI 本身不会精读论文、判断学术价值或自动写出可信解读；需要具备联网、读文件和执行工具能力的 Agent。项目不内置付费模型服务或 API 密钥。

## 安装

需要 **Python 3.11 或更新版本**。克隆或下载仓库，在项目目录运行：

macOS：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python scripts/paper_daily.py doctor
```

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts/paper_daily.py doctor
```

使用 Agent 自带的 skill 安装功能，或把本仓库放入它支持的技能目录。也可以通过本地复制工具指定父目录：

```text
python scripts/install_skill.py --dest /path/to/skills
```

工具会创建该目录下的 `paper-research-daily` 文件夹。Windows 可以使用带引号的本地路径；上述 `python` 应使用已安装依赖的虚拟环境解释器。更多说明见 [系统与 Agent 适配](references/adapters.md)。没有技能发现功能的 Agent，可以显式读取 `SKILL.md` 并按需读取引用文件。

## 从自己的课题开始

可以直接告诉 Agent：

> 使用 paper-research-daily。我关注有限数据下的可靠学习，请帮我确定研究范围与筛选标准。每天为我整理文献，先展示配置让我确认，再开始执行。输出中文，日期按北京时间。

Agent 会结合你的背景提出配置，而不是直接套用宽泛关键词。也可先创建草案：

```text
python scripts/paper_daily.py init --profile ./my-profile.json --topic "有限数据下的可靠学习" --root ./my-literature --language zh-CN --timezone Asia/Shanghai
python scripts/paper_daily.py check-profile --profile ./my-profile.json
```

实际确认标准后，再记录确认状态：

```text
python scripts/paper_daily.py confirm --profile ./my-profile.json
```

`confirm` 只记录已有的用户决定，不会独立询问或证明用户同意。配置改动会使原确认指纹失效，需要重新确认。个人配置与文献库应放在公开仓库之外；相对文献库路径以配置文件所在目录为基准。

## 默认标准

| 项目 | 初始设置 |
| --- | --- |
| 每日篇数 | 8 篇 |
| 工作日 | 4 篇新文＋4 篇正式发表 |
| 周末 | 备选池＋当天候选综合 Top 8 |
| 新文发现 | 仅 arXiv，可按领域修改 |
| 新文窗口 | 优先 72 小时，不足扩大至 7 天 |
| 六维评分 | 匹配 35、证据 25、启发 20、创新 10、代表性 5、复现 5 |
| 推荐门槛 | 总分 75、匹配度 25，必须有理由 |
| 阅读深度 | 默认全文、高密度卡片；支持中文与英文 |
| 活跃备选 | 最多 100 条，14 天复评 |
| 定时 | 默认关闭，手动运行 |

分数是有依据的编辑判断，不是精确测量。理论论文、实验论文、数据集和综述使用适合各自类型的证据标准。名气和引用量不代替内容评价。

首次公告、提交、修订、在线发表、正式卷期日期分别记录。预印本有 DOI 不代表经过同行评审。检索失败不能解释为没有新文；质量不足时如实报告缺项，不降低标准凑数。v0.1 会保留未满额的预备材料，但不会将其发布为完整日报。备选池数量与复评周期由 Agent 按规则管理，Python 不会自动判断质量或清理候选。细则见 [首次配置](references/onboarding.md) 和 [筛选规则](references/selection.md)。

## 输出结构

```text
my-literature/
├── YYYY-MM-DD/
│   ├── 00_overview.md
│   ├── 01_...pdf
│   ├── metadata.json
│   └── search_log.json
├── index.md
├── pool.md
├── pending.md
├── archive.md
├── registry.json
└── .work/
```

总览按阅读优先级排列。每篇保留作者、题录、版本、PDF／DOI 入口、一句话定位，以及九个内容部分和评分理由：摘要中文转述、研究问题、核心方法、相对创新、带章节页码的证据表、局限、对课题的用途、可验证的下一步、阅读与复现入口。中文通常每篇 1,200–1,800 字，按内容调整，不凑字。

作者结论、独立分析和建议实验明确分开。摘要级阅读不会写成全文精读；代码入口核对到具体论文，未运行就不宣称复现成功。下载失败保留已核验 DOI 或官方入口。

## 工具命令

通过 `python scripts/paper_daily.py 命令 --help` 查看参数；虚拟环境激活后也可使用 `paper-daily`。

| 命令 | 用途 |
| --- | --- |
| `init`、`check-profile`、`confirm` | 创建配置、检查配置、记录确认 |
| `scan` | 在下载新候选前登记已有 PDF |
| `search` | 从 arXiv／arXiv 最新列表／Crossref／OpenAlex 获取候选 |
| `download` | 下载并检查 PDF |
| `prepare` | 保存预备阅读材料，不写推荐历史 |
| `pool` | 更新备选、待核验与归档记录 |
| `publish` | 根据 Agent 完成的记录生成日报并更新文献库 |
| `validate` | 校验全库与指定日期的产物 |
| `doctor` | 检查 Python 依赖和时区支持 |

检索输出只是待核验候选，不能直接当作精读日报发布。输入支持数组或 `{"papers": [...]}`，字段见 [候选记录说明](references/candidate-schema.md)。仓库示例为明确标注的虚构示例，不可作为真实学术证据发布。

## 定时与跨平台

可接入 Agent 应用自身的自动化、macOS `launchd`、Windows 任务计划程序或其他运行器。定时任务必须唤醒实际 Agent；单独定时运行 Python 存储工具不会自动完成检索与阅读。默认不会安装持久任务，配置中的时间也不会自行启用调度。时区、夏令时、预备／终筛与恢复规则见 [定时说明](references/scheduling.md)。

核心工具采用标准 Python，仓库 CI 配置覆盖 macOS、Windows 和多个 Python 版本。以实际 Actions 结果为准；存在测试配置不等于已经通过。技能遵循 [Agent Skills 规范](https://agentskills.io/specification)，不同 Agent 的安装、工具权限和定时能力仍需适配，未声称所有 Agent 均经过端到端测试。

本地测试：

```text
python -m pip install -e ".[test]"
python -m pytest -q
```

## 隐私、参考与许可证

默认只保存本地，不自动上传文献库、发邮件、登录账号或安装定时任务。密码、Cookie、令牌、私人 PDF 与阅读历史不应进入公开包。机构访问使用宿主已获授权的会话；需要人工验证的论文可以暂存待处理，其他论文继续。

流程参考了 [arxiv](https://smithery.ai/skills/lianggs8/arxiv)、[paper-daily](https://smithery.ai/skills/su-lan/paper-daily)、[paper-read-skill](https://github.com/Ayanami0730/paper-read-skill) 与 [nature-academic-search](https://github.com/Yuan1z0825/nature-skills/tree/main/skills/nature-academic-search)。它们不是运行依赖，项目不会自动安装。此处代码与文档独立编写；第三方论文和服务遵循各自条款。

项目采用 [MIT 许可证](LICENSE)。
