# AI Blog Studio 交接文档

更新时间：2026-05-29

## 0. 基本信息

```text
服务器 IP:       10.10.130.82
SSH 用户:        root
服务器密码:      hongxuan

项目目录:        /root/ai-blog-studio
线上地址:        http://10.10.130.82:4174
服务端口:        4174
启动日志:        /root/ai-blog-studio/server.log
PID 文件:        /root/ai-blog-studio/server.pid
```



服务器启动命令：

```bash
cd /root/ai-blog-studio
PYTHONPATH=/root/ai-blog-studio/vendor nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 4174 > server.log 2>&1 &
echo $! > server.pid
```

停止服务：

```bash
cd /root/ai-blog-studio
if [ -f server.pid ]; then
  kill "$(cat server.pid)" || true
  rm -f server.pid
fi
```

端口确认：

```bash
ss -ltnp | grep -E ':(4174|8013) '
```

## 1. 项目说明

这是一个本地优先的 AI Blog 生成工具，主要用于生成面向 AI 检索曝光的电商 Blog。

整体形态是：

```text
FastAPI 后端 + 静态前端 + 本地 JSON 配置和文章库
```

前端负责输入、展示、选择参考资料、编辑大纲和保存文章；后端负责模型调用、联网参考搜索、意图分析、大纲生成、正文分段生成、内容评分、内容迭代和文章持久化。

## 2. 目录和关键文件

核心目录：

```text
backend/
  main.py                         FastAPI 路由入口，负责 API 和静态页面服务
  settings.py                     项目路径、默认配置、默认 prompt
  services/
    model_client.py               模型 API 调用层，支持 OpenAI-compatible、Claude、Gemini、自定义 JSON
    generator.py                  意图分析、大纲、正文生成、评分、内容迭代的主逻辑
    reference_search.py           联网参考搜索、搜索规划、结果排序、图片占位接口
    storage.py                    配置读写、文章 JSON 存储、版本管理

public/
  index.html                      单页前端结构
  app.js                          前端交互、API 请求、页面状态
  styles.css                      前端样式

frontend-src/
  app.ts                          后续 TypeScript 迁移草稿，目前运行链路仍使用 public/app.js

data/
  config.json                     API 卡片、模型分配、prompt、搜索配置
  blogs/                          已生成文章和版本，按 JSON 文件保存

output/
  *.log                           本地测试或运行日志

run.py                            本地启动入口
start_local.bat                   Windows 本地启动器
requirements.txt                  Python 依赖
README.md                         简要运行说明
DEPLOYMENT.md                     部署记录和服务器操作说明
```

## 3. 整体 Workflow

**生成blog**

```
用户在前端填写商品信息/需求
  → [可选] POST /api/search-references    联网搜索相关参考页面（SearXNG / newsfilter）
  → [可选] POST /api/intent-analysis      分析用户意图，识别目标受众和写作方向
  → [可选] POST /api/title-options        生成 SEO/GEO 双轨候选标题，用户选择
  → POST /api/outline                     根据需求+参考资料生成结构化大纲（H1/H2/H3）
  → 用户确认或编辑大纲
  → POST /api/generate/stream             按章节分段生成正文（流式推送进度）
      ↳ 内部自动：生成 SEO 版 + GEO 版双轨正文
      ↳ 内部自动：evaluator 打 v0 基准分
      ↳ 内部自动：revision 执行一轮修改，打 v1 分
  → 自动保存到文章库 POST /api/blogs
```

**利用迭代工具对blog优化**

```
在文章库中选择已有文章
  → POST /api/score                        60 项 EEAT 评分 + GPTZero AI 检测
  → 查看评分报告（itemScores、修改建议、强弱项）
  → POST /api/adversarial-train/stream     按章节分段重写（流式推送进度）
      ↳ 将 EEAT 建议 + GPTZero 提示注入 revision prompt
      ↳ 修改完自动打分，保存为新版本
  → 可多轮迭代，每轮对应一个版本记录
  → POST /api/score/compare                对比两个版本的评分差异，确认改进效果
```

## 4. 本地运行

默认本地地址：

```text
http://127.0.0.1:4173
```

也可以双击：

```text
start_local.bat
```

启动器菜单：

```text
1. Start          启动服务
2. Check status   检查服务
3. Stop           停止服务
4. Restart        重启服务
5. Exit           退出
```

## 5. 服务器部署信息

服务器：

```text
10.10.130.82
```

服务器项目目录：

```text
/root/ai-blog-studio
```

线上访问地址：

```text
http://10.10.130.82:4174
```

当前服务端口：

```text
4174
```

## 6. 必要配置

主配置文件：

```text
data/config.json
```

里面主要有四类配置：

```text
language                  界面/默认输出语言，目前支持 zh / en
apiProfiles               API 卡片，含 endpoint、apiKey、headersJson、可用模型
taskAssignments           不同任务使用哪个 API 卡片和模型
prompts                   中文/英文 prompt
searchSettings            联网参考搜索配置
```

当前模型模式：

```text
anthropic_messages
```

当前主要模型：

```text
claude-sonnet-4-6
```

配置注意事项：

- `data/config.json` 含 API Key，不要把密钥贴到聊天、文档、截图或日志里。
- 前端通过 `GET /api/config` 读取配置时，后端会把 API Key 显示为 `********`。
- 保存配置走 `PUT /api/config`，如果前端传回 `********`，后端会保留原密钥，不会覆盖为空。
- 如果新增任务类型，需要同时检查 `backend/services/model_client.py` 的 `TASK_LABELS`、任务分配、默认配置和前端设置项。
- 没有配置 API 卡片、任务没分配模型、缺 endpoint/API Key/模型名时，后端会直接报错，不会 mock 生成。

搜索配置：

```text
newsfilterEndpoint: http://10.10.130.82:8000/api/test/query
searxngEndpoint:    http://10.10.130.82:8080
maxResults:         15
timeoutSeconds:     25
```

搜索逻辑：

- 先由 `search_planner` 任务规划 3-5 个商品/场景查询词。
- 优先请求 `newsfilterEndpoint`。
- `newsfilter` 失败或结果不足时，降级请求 SearXNG。
- 搜索结果会过滤低价值站点、按相关性和权重重新排序，最多返回 20 条。



## 模块设置

### 搜索模块

**接口**：`POST /api/search-references`

**请求参数**（JSON body）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| language | string | 否 | 语言，`zh` 或 `en`，默认 `zh` |
| productType | string | 否 | 商品品类，如"便携露营灯" |
| productName | string | 否 | 商品名称，如"BioLite BaseLantern+" |
| market | string | 否 | 目标市场，如"中国" |
| promotionGoal | string | 否 | 推广目标，如"AI检索曝光" |
| manualQuery | string | 否 | 手动指定搜索词（指定后跳过 AI 规划） |
| maxResults | int | 否 | 最终返回数量，默认 20 |
| analysisMaxResults | int | 否 | 内部搜索候选数量，默认 80 |
| requirement | object | 否 | 可内嵌上述字段的完整需求对象 |

**主要逻辑**：

1. 调用 `search_planner` 模型，从用户需求自动规划 4-8 个搜索词和 3-6 个核心实体词
2. 优先请求 newsfilter；失败或结果不足时降级到 SearXNG
3. 合并用户自定义来源（`searchSettings.customerSources`，按权重注入指定 URL）
4. 算法重排：综合相关性、语言匹配、来源权威性等多维打分，过滤零相关性结果
5. 返回排序后参考列表（`items`）和分析用完整列表（`analysisItems`）

**返回格式**：
```json
{
  "query": "主搜索词",
  "items": [
    {
      "id": "sha1[:16]",
      "rank": 1,
      "weightedRank": 1,
      "score": 23.45,
      "displayScore": 78,
      "title": "文章标题",
      "url": "https://example.com/...",
      "domain": "example.com",
      "snippet": "摘要文本",
      "thumbnail": "",
      "publishTime": "2025-01-01",
      "sourceRelevance": 0.85
    }
  ],
  "analysisItems": [...],
  "errors": [],
  "meta": {
    "query": "主搜索词",
    "coreTerms": ["核心词1", "核心词2"],
    "searchVariants": ["变体词1"],
    "sources": [{"mode": "searxng", "seconds": 2.1}]
  }
}
```

**调用示例**：
```bash
curl -X POST http://10.10.130.82:4174/api/search-references \
  -H 'Content-Type: application/json' \
  -d '{"language":"zh","productType":"便携露营灯","market":"中国","maxResults":10}'
```

---

### 意图识别模块

**接口**：`POST /api/intent-analysis`

**请求参数**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| language | string | 否 | `zh` / `en` |
| requirement | object/string | 否 | 完整用户需求（含 productType/productName/market 等） |
| references | array | 否 | 搜索模块返回的参考资料列表 |

**主要逻辑**：调用 `outline` 任务模型，分析需求与参考资料，输出推荐写作主题列表、最优主题、目标受众和搜索意图标签，作为大纲生成的输入参考。

**返回格式**：
```json
{
  "topics": ["主题A", "主题B"],
  "selectedTopic": "推荐主题",
  "searchIntent": "informational",
  "audience": "目标受众描述"
}
```


---

### 大纲生成模块

**接口**：`POST /api/outline`

**请求参数**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| language | string | 否 | `zh` / `en` |
| requirement | object | 否 | 商品信息和用户需求 |
| references | array | 否 | 选中的参考资料 |
| intent | object | 否 | 意图分析结果 |
| selectedTitle | object | 否 | 用户选中的 SEO/GEO 候选标题 |

**主要逻辑**：调用 `outline` 模型，结合参考资料中的实体情报，生成同时面向 SEO 排名和 GEO/AI 检索引用的结构化大纲，重点关注低覆盖率实体和信息缺口。

**返回格式**：
```json
{
  "topics": ["主题A"],
  "selectedTopic": "推荐主题",
  "searchIntent": "commercial",
  "audience": "目标受众",
  "outline": {
    "title": "文章 H1 标题",
    "sections": [
      {
        "h2": "章节标题",
        "summary": "本节要点摘要",
        "h3": ["子标题1", "子标题2"],
        "targetEntities": ["实体1"],
        "seoPurpose": "SEO 目的说明",
        "geoPurpose": "GEO 目的说明"
      }
    ]
  },
  "entityQuestions": ["用户子问题1"],
  "sourceAngles": ["来源角度1"],
  "aiExposureNotes": "AI 引用建议"
}
```

---

### 正文生成模块

**接口（流式，前端默认使用）**：`POST /api/generate/stream`

**接口（非流式）**：`POST /api/generate`

**请求参数**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| language | string | 否 | `zh` / `en` |
| requirement | object | 否 | 商品信息和需求 |
| outline | object | 是 | 大纲生成结果 |
| references | array | 否 | 选中的参考资料（`useAs:"link"` 引用链接 / `useAs:"style"` 样式参考） |
| track | string | 否 | `seo` 或 `geo`，决定写作 prompt 套路 |
| images | array | 否 | 图片列表（按 Markdown 章节位置插入） |
| autoScore | bool | 否 | 是否自动打分，默认 true |
| autoRevise | bool | 否 | 是否自动执行一轮修改，默认 true |

**主要逻辑**：

- H2 章节 ≤ 2 时一次整体请求；否则逐章节调用模型（防 HTTP 524 超时）
- SEO 版和 GEO 版正文均生成（双轨）
- 每章节生成后推送 SSE 事件，前端实时显示进度
- 完成后自动打 v0 基准分，执行一轮修改后打 v1 分，最终自动保存到文章库

**流式事件格式（SSE data 字段）**：
```json
{"type":"progress","stage":"article_seo_section","section":1,"total":4,"content":"当前章节 Markdown"}
{"type":"progress","stage":"score_v0","score":72.5,"evaluation":{...}}
{"type":"progress","stage":"revision_section","section":2,"total":4}
{"type":"progress","stage":"score_v1","score":78.0,"evaluation":{...}}
{"type":"progress","stage":"complete","article":"...","seoArticle":"...","geoArticle":"...","blogId":"uuid"}
{"type":"error","stage":"error","message":"错误信息","statusCode":502}
```


---

### 生成文章管理模块

**接口列表**：

| 方法 | URL | 说明 |
|------|-----|------|
| GET | /api/blogs | 列出所有文章（按更新时间倒序） |
| POST | /api/blogs | 创建/保存新文章 |
| GET | /api/blogs/{id} | 获取单篇文章完整数据 |
| PUT | /api/blogs/{id} | 更新文章（部分字段更新） |
| DELETE | /api/blogs/{id} | 删除文章（物理删除 JSON 文件） |
| POST | /api/blogs/{id}/versions | 基于现有文章创建新版本（同组 versionIndex +1） |
| PUT | /api/blog-groups/{group_id} | 修改文章组名称（批量更新同组所有文章） |

**文章 JSON 字段结构**：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | UUID |
| title | string | 文章标题 |
| createdAt / updatedAt | string | ISO8601 时间 |
| language | string | `zh` / `en` |
| input | object | 原始用户输入（requirement + references） |
| plan | object | 大纲（outline 对象） |
| article | string | 完整 Markdown 正文（默认为 SEO 版） |
| seoArticle | string | SEO 版正文 |
| geoArticle | string | GEO 版正文 |
| evaluation | object | 评分结果（score + rounds 数组） |
| groupId / groupName | string | 文章组标识（同主题多版本关联） |
| versionIndex | int | 版本序号（从 1 开始） |
| versionLabel | string | 版本标签，如"v1" |

**存储路径**：`data/blogs/{id}.json`（每篇独立 JSON 文件）

---

### 文章自动迭代模块

**接口（流式）**：`POST /api/adversarial-train/stream`

**接口（非流式）**：`POST /api/adversarial-train`

**请求参数**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| article | string | 是 | 当前正文 Markdown |
| evaluation | object | 否 | 上一次评分结果（含修改建议） |
| language | string | 否 | `zh` / `en` |
| requirement | object | 否 | 原始用户需求（提供写作上下文） |
| rounds | int | 否 | 迭代轮数，默认 1 |

**主要逻辑**：按 Markdown H2 拆分文章为章节，逐章节调用 `revision` 模型，将 EEAT 评分建议和 GPTZero 提示注入 prompt 后重写。每轮修改完成后调用 `evaluator` 打分，结果保存为新版本。

---

### 文章打分模块

**打分接口**：`POST /api/score`

**比较接口**：`POST /api/score/compare`

**POST /api/score 请求参数**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| article | string | 是 | 待评分的正文 Markdown |
| language | string | 否 | `zh` / `en` |

**主要逻辑**：

1. **规则引擎**（纯 Python，本地 < 1 秒）：对 60 项 EEAT checklist 中可机械判断的项做规则检测，标记为 `locked=true`
2. **LLM 评分**（调用 `evaluator` 模型，约 25-33 秒）：对软性项进行判断，规则项结果优先
3. **GPTZero**（可选）：若 `gptZeroSettings.enabled=true` 且配置了 API Key，检测 AI 写作概率，以 `weight`（默认 0.35）合并进总分

**返回格式**：
```json
{
  "score": 74.5,
  "contentType": "review",
  "itemScores": [
    {"id":"E1","score":1,"evidence":"第一人称表述出现 3 次","suggestion":"...","locked":true}
  ],
  "strengths": ["实体覆盖充分"],
  "risks": ["AI 写作概率偏高"],
  "revisionAdvice": "建议加强 Trustworthiness 板块",
  "gptzeroResult": {
    "completely_generated_prob": 0.45,
    "human_written_prob": 0.55
  }
}
```

**POST /api/score/compare 参数**：`{"articles": ["版本A正文", "版本B正文"], "language": "zh"}`

返回两个版本的评分结果和差异摘要。

---

### 全局配置管理模块

**接口**：

| 方法 | URL | 说明 |
|------|-----|------|
| GET | /api/config | 读取配置，API Key 返回 `********` |
| PUT | /api/config | 更新配置，传入 `********` 时保留原密钥不覆盖 |

**配置结构（data/config.json 主要字段）**：

| 字段 | 类型 | 说明 |
|------|------|------|
| language | string | 默认语言，`zh` 或 `en` |
| apiProfiles | array | API 卡片列表（id/name/mode/endpoint/apiKey/headersJson/availableModels） |
| taskAssignments | object | 各任务绑定的卡片和模型（outline/article/evaluator/revision/optimizer/search_planner/entity_extractor/image） |
| prompts | object | 按语言存储的 prompt（`prompts.zh.*`） |
| searchSettings | object | 搜索配置（newsfilterEndpoint/searxngEndpoint/maxResults/timeoutSeconds/customerSources 等） |
| gptZeroSettings | object | GPTZero 配置（endpoint/apiKey/enabled/weight） |

**支持的 API mode**：

| mode | 说明 |
|------|------|
| openai_chat | OpenAI Chat Completions 格式（兼容 DeepSeek、MiniMax 等） |
| anthropic_messages | Anthropic Messages API 格式 |
| gemini_generate_content | Google Gemini generateContent 格式 |
| openai_responses | OpenAI Responses API 格式 |
| custom_json | 自定义 JSON 请求体（bodyTemplate 字段填写模板） |
这个参数包括两部分，第一部分是运行过程中传入的参数，和生成业务有关，包括需求，标题，正文文字等

**业务参数（每次生成由用户填写，前端构建后传入后端）**：

| 参数名 | 字段 | 说明 |
|--------|------|------|
| 商品名称 | productName | 如"BioLite BaseLantern+" |
| 商品品类 | productType | 如"便携露营灯" |
| 目标市场 | market | 如"中国"、"美国" |
| 推广目标 | promotionGoal | 如"AI检索曝光"、"SEO排名" |
| 关键词 | keywords | 核心关键词列表 |
| 补充说明 | brief | 额外说明或商品资料文本 |
| 参考资料 | references | 从搜索结果中选中的链接（`useAs:"link"` 引用链接 / `useAs:"style"` 样式参考） |
| 生成轨道 | track | `seo` 或 `geo`，决定使用哪套写作 prompt |
| 语言 | language | `zh` 或 `en` |
| 已选大纲 | outline | 大纲生成接口返回的对象 |
| 已选标题 | selectedTitle | 标题生成接口返回的 `{seo, geo}` 对象 |

第二种属于超参数，是预设在系统内部，和业务无关，每次工作只需要调用就行。包括全部的prompt，api key，搜索引擎等。

**超参数（存于 data/config.json，通过前端设置页面管理，后端调用时自动读取）**：

| 参数 | 配置路径 | 说明 |
|------|----------|------|
| 大纲 Prompt | prompts.zh.outline | 大纲生成指令 |
| 正文 Prompt | prompts.zh.article | 正文写作指令 |
| 评分 Prompt | prompts.zh.optimizer | EEAT 评分指令 |
| 修改 Prompt | prompts.zh.revision | 修改重写指令 |
| 标题 Prompt | prompts.zh.title | 双轨标题生成指令 |
| 实体抽取 Prompt | prompts.zh.entity_extractor | 实体抽取指令 |
| 搜索规划 Prompt | prompts.zh.search_planner | 搜索词规划指令 |
| API Key | apiProfiles[].apiKey | 各模型 API 密钥 |
| API Endpoint | apiProfiles[].endpoint | 模型 API 地址 |
| 模型分配 | taskAssignments.* | 各任务绑定的 API 卡片和模型 |
| newsfilter 端点 | searchSettings.newsfilterEndpoint | newsfilter 搜索服务地址 |
| SearXNG 端点 | searchSettings.searxngEndpoint | SearXNG 搜索服务地址 |
| GPTZero Key | gptZeroSettings.apiKey | GPTZero API 密钥 |
| GPTZero 权重 | gptZeroSettings.weight | GPTZero 分数在总分中的权重 |

### 存储说明

当前存储主要分为两部分，第一部分是主体模块，也就是生成的blog。这里我统一将文档使用md格式存储在服务器

**文章存储（data/blogs/）**：

- 路径：`data/blogs/{uuid}.json`，每篇文章独立一个 JSON 文件
- 格式：JSON（包含完整元数据和正文 Markdown）
- 版本管理：同组多版本通过 `groupId` + `versionIndex` 关联，各版本独立存文件
- 异常容错：`GET /api/blogs` 列表接口会跳过解析失败的文件，不影响其余文章
- 注意：`data/blogs/` 是用户资产，服务器同步时不要删除或覆盖线上文章

第二部分是超参数，包括api，prompt，还有其他相关的设置，调用方式如下：

**配置存储（data/config.json）**：

- 路径：`data/config.json`（单文件，JSON 格式）
- 读取接口：`GET /api/config`（API Key 脱敏为 `********`）
- 写入接口：`PUT /api/config`（传入 `********` 时保留原密钥，不覆盖为空）
- 后端内部：通过 `read_config(mask_key=False)` 获取明文密钥用于 API 调用
- 安全注意：config.json 含明文 API Key，不要提交到公共代码仓库或粘贴到截图



## 8. 前端参数与存储说明

#### 前端中需要传入的参数说明

这个参数包括两部分，第一部分是运行过程中传入的参数，和生成业务有关，包括需求，标题，正文文字等

**业务参数（每次生成由用户填写，前端构建后传入后端）**：

| 参数名 | 字段 | 说明 |
|--------|------|------|
| 商品名称 | productName | 如"BioLite BaseLantern+" |
| 商品品类 | productType | 如"便携露营灯" |
| 目标市场 | market | 如"中国"、"美国" |
| 推广目标 | promotionGoal | 如"AI检索曝光"、"SEO排名" |
| 关键词 | keywords | 核心关键词列表 |
| 补充说明 | brief | 额外说明或商品资料文本 |
| 参考资料 | references | 从搜索结果中选中的链接（`useAs:"link"` 引用链接 / `useAs:"style"` 样式参考） |
| 生成轨道 | track | `seo` 或 `geo`，决定使用哪套写作 prompt |
| 语言 | language | `zh` 或 `en` |
| 已选大纲 | outline | 大纲生成接口返回的对象 |
| 已选标题 | selectedTitle | 标题生成接口返回的 `{seo, geo}` 对象 |

第二种属于超参数，是预设在系统内部，和业务无关，每次工作只需要调用就行。包括全部的prompt，api key，搜索引擎等。

**超参数（存于 data/config.json，通过前端设置页面管理，后端调用时自动读取）**：

| 参数 | 配置路径 | 说明 |
|------|----------|------|
| 大纲 Prompt | prompts.zh.outline | 大纲生成指令 |
| 正文 Prompt | prompts.zh.article | 正文写作指令 |
| 评分 Prompt | prompts.zh.optimizer | EEAT 评分指令 |
| 修改 Prompt | prompts.zh.revision | 修改重写指令 |
| 标题 Prompt | prompts.zh.title | 双轨标题生成指令 |
| 实体抽取 Prompt | prompts.zh.entity_extractor | 实体抽取指令 |
| 搜索规划 Prompt | prompts.zh.search_planner | 搜索词规划指令 |
| API Key | apiProfiles[].apiKey | 各模型 API 密钥 |
| API Endpoint | apiProfiles[].endpoint | 模型 API 地址 |
| 模型分配 | taskAssignments.* | 各任务绑定的 API 卡片和模型 |
| newsfilter 端点 | searchSettings.newsfilterEndpoint | newsfilter 搜索服务地址 |
| SearXNG 端点 | searchSettings.searxngEndpoint | SearXNG 搜索服务地址 |
| GPTZero Key | gptZeroSettings.apiKey | GPTZero API 密钥 |
| GPTZero 权重 | gptZeroSettings.weight | GPTZero 分数在总分中的权重 |

#### 存储说明

当前存储主要分为两部分，第一部分是主体模块，也就是生成的blog。这里我统一将文档使用md格式存储在服务器

**文章存储（data/blogs/）**：

- 路径：`data/blogs/{uuid}.json`，每篇文章独立一个 JSON 文件
- 格式：JSON（包含完整元数据和正文 Markdown）
- 版本管理：同组多版本通过 `groupId` + `versionIndex` 关联，各版本独立存文件
- 异常容错：`GET /api/blogs` 列表接口会跳过解析失败的文件，不影响其余文章
- 注意：`data/blogs/` 是用户资产，服务器同步时不要删除或覆盖线上文章

第二部分是超参数，包括api，prompt，还有其他相关的设置，调用方式如下：

**配置存储（data/config.json）**：

- 路径：`data/config.json`（单文件，JSON 格式）
- 读取接口：`GET /api/config`（API Key 脱敏为 `********`）
- 写入接口：`PUT /api/config`（传入 `********` 时保留原密钥，不覆盖为空）
- 后端内部：通过 `read_config(mask_key=False)` 获取明文密钥用于 API 调用
- 安全注意：config.json 含明文 API Key，不要提交到公共代码仓库或粘贴到截图

## 9. 主要功能链路

### 6.1 Blog 生成

用户流程：

```text
输入需求/商品资料
-> 联网参考搜索
-> 意图分析/主题选择
-> 大纲生成
-> 用户确认或编辑大纲
-> 分段生成正文
-> 保存到文章库
```

关键接口：

```text
POST /api/search-references
POST /api/intent-analysis
POST /api/outline
POST /api/generate
POST /api/generate/stream
```

前端默认使用流式接口：

```text
POST /api/generate/stream
```

后端会按大纲章节分段请求模型，降低长文一次性生成导致的 HTTP 524 或网关超时概率。

### 6.2 参考资料

参考资料有两种用途：

```text
引用链接        进入正文，要求模型在相关段落自然插入 Markdown 超链接
样式参考        只学习结构、段落节奏、标题方式和信息密度，不要求照抄
```

相关逻辑在：

```text
backend/services/reference_search.py
backend/services/generator.py 的 reference_context()
public/app.js
```

### 6.3 内容评分和迭代

内容迭代链路：

```text
选择或输入文章
-> 评价 AI 打分和给建议
-> 修改 AI 按 Markdown 章节分段改写
-> 每轮输出可保存为文章版本
```

关键接口：

```text
POST /api/score
POST /api/score/compare
POST /api/adversarial-train
POST /api/adversarial-train/stream
```

目前迭代不是改 prompt，而是直接改正文。相关防呆在 `generator.py` 里：如果模型返回旧格式的 `updatedPrompt`，后端会尝试修复或报错。

### 6.4 文章库和版本

文章保存在：

```text
data/blogs/*.json
```

每篇文章包含：

```text
id
title
createdAt / updatedAt
input
plan
article
evaluation
rounds
language
groupId / groupName / versionIndex / versionLabel
```

关键接口：

```text
GET    /api/blogs
GET    /api/blogs/{id}
POST   /api/blogs
PUT    /api/blogs/{id}
DELETE /api/blogs/{id}
POST   /api/blogs/{id}/versions
PUT    /api/blog-groups/{group_id}
```

维护注意：

- `data/blogs/` 是用户资产，不要随便删除。
- 同步服务器时不要对 `data/blogs/` 做删除式同步，除非明确要清空线上文章库。
- 如果文章 JSON 损坏，列表接口会跳过坏文件；打开单篇时可能 404 或 JSON 解析失败。

### 6.5 图片功能

接口：

```text
POST /api/generate-image
```

当前状态，还没有接入生图api，预留了接口：

```text
占位接口，返回 pending_provider
```

接入真实图片模型的位置：

```text
backend/services/reference_search.py 的 generate_image_placeholder()
```

前端入口已做，上传图片会按 Markdown 章节位置插入，不再统一放到文末。

## 10. 维护和修改流程

推荐流程：

```text
1. 本地修改
2. 本地启动测试
3. 备份服务器当前版本
4. 同步到服务器
5. 重启 4174 服务
6. 低消耗验证
```

不要在服务器上直接改代码，避免本地和服务器版本漂移。

通常需要同步的内容：

```text
backend/
public/
data/config.json
run.py
requirements.txt
README.md
DEPLOYMENT.md
start_local.bat
```

谨慎同步：

```text
data/blogs/
```

除非明确要迁移文章库，否则不要覆盖或删除服务器上的文章。

服务器上一次已记录的备份：

```text
/root/ai-blog-studio/backups/pre_deploy_20260520_175857.tar.gz
```

后续每次部署前建议重新打包备份：

```bash
cd /root
tar -czf /root/ai-blog-studio/backups/pre_deploy_$(date +%Y%m%d_%H%M%S).tar.gz ai-blog-studio
```



## 12. 常见问题排查

### 9.1 页面打不开

先确认服务是否启动：

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:4173/api/config" -UseBasicParsing -TimeoutSec 2
```

如果本地端口被占用：

```powershell
Get-NetTCPConnection -LocalPort 4173 -State Listen
```

本地最省事处理方式是用 `start_local.bat` 的 Stop / Restart。

### 9.2 模型接口报错

优先检查：

```text
data/config.json
```

重点看：

```text
apiProfiles[].endpoint
apiProfiles[].apiKey
apiProfiles[].headersJson
taskAssignments
模型名是否存在
```

常见报错：

- `请先为某任务分配 API 卡片`：任务没有绑定 API 卡片。
- `缺少 endpoint 或 API Key`：API 卡片不完整。
- `请在 API 卡片中配置模型名`：任务分配里没有模型。
- `Extra Headers JSON 格式无效`：headersJson 不是合法 JSON。
- `HTTP 524`：上游模型或代理超时，通常重试、换快模型或降低单段内容长度。

### 9.3 搜索没有结果

优先检查：

```text
searchSettings.newsfilterEndpoint
searchSettings.searxngEndpoint
searchSettings.timeoutSeconds
```

逻辑上 `newsfilter` 不可用时会自动降级到 SearXNG。如果两边都失败，接口返回的 `errors` 字段会说明原因。

另一个常见原因是搜索规划模型没配好。`search_planner` 默认会复用大纲任务，但如果配置被改乱，也会影响搜索词质量。

### 9.4 大纲或评分 JSON 解析失败

大纲、意图分析、评分等接口要求模型返回严格 JSON。若失败：

- 先看对应 prompt 是否被改得过于宽松。
- 检查模型是否倾向输出 Markdown 代码块或解释文字。
- `generator.py` 已有 JSON 修复逻辑，但修复不是万能的。

### 9.5 正文生成很慢

这是预期范围内的问题。后端超时时间设置较长：

```text
MODEL_REQUEST_TIMEOUT = 1200
MODEL_MAX_ATTEMPTS = 3
```

正文和迭代都已经分段生成，前端会显示进度。如果仍然慢，优先考虑：

- 换更快模型。
- 缩短大纲章节。
- 降低迭代轮数。
- 减少一次性输入的参考资料和图片。

### 9.6 文章库异常

文章文件在：

```text
data/blogs/
```

可以先定位最近修改的 JSON。文章列表会跳过解析失败的文件，所以如果列表少文章，优先怀疑某个 JSON 文件损坏或字段缺失。

## 13. 问题与说明

1.当前全部使用的是claude模型，现在最核心的开销是大模型摘取entity的过程，这个过程可以考虑换成更便宜的Deepseek

> **补充**：entity_extractor 任务已配置 DeepSeek（endpoint: https://ai.deeplumen.io，model: deepseek-chat），实现和主模型解耦。DeepSeek 约 1元/M 输入 + 2元/M 输出，比 Claude 主模型便宜约 10 倍，实测每次实体抽取约消耗 2000 token，成本可忽略不计。

2.当前使用的搜索工具和过滤器是之前开发的一个算法，除了搜索，过滤，排序功能之外，之前还加入过一个能将客户信息直接加权插入搜索结果并提高权重的模块，这个当前还没有实现，后续可以考虑加上。

> **补充**：客户信息加权插入已实现，对应 `searchSettings.customerSources` 字段。可在配置中添加多组客户来源（URL 列表），每组指定 `name`、`enabled`、`weight`（默认 3），搜索时这些 URL 会以加权分数（`10 + weight + 相关性分`）直接插入候选列表参与最终排序。

3.当前的评价模块计划使用gptzero和大模型预设规则统一打分，现在有两个问题，第一个是gptzero还未注册账号获取api，返回结果也未知，只预留了本地接口，需要结合具体返回值再安排。第二个是当前gptzero不支持中文检查，这个需要考虑后续中文生成的场景多不多，如果不多可以不用管这个。

> **补充**：GPTZero API 已接入，API Key 为 `8a24eb826d164608a4d99eacfbed4cbc`，配置在 `gptZeroSettings`。返回字段中 `completely_generated_prob`（AI 生成概率）和 `human_written_prob`（人类写作概率）已映射进打分模块。中文检测准确率确实偏低，当前以 weight=0.35 的较低权重合并，影响有限；若中文场景为主可考虑换用 Originality.ai 或开源 Binoculars 方案。

4.当前搜索的过滤模块并没有整理清楚，当前过滤模块主要工作是将初步过滤排序后的结果进行二次过滤，主要是滤掉和业务完全无关的内容，如果不加入过滤那么会返回和业务无关的结果，包括百科，范围很广的网站（旅游网站，攻略网站）。如果过滤很严就会把所有结果过滤走，对于很大众或者需求很多的要求会很难剩下结果。

所以这个需要结合业务，到底需不需要这些和业务无关的，偏向于广度的知识和链接。

5.当前架构生成出来的文章和竞品相比，在我们预设的评价体系上已经可以基本超过，这些可以结合后续业务，重新让竞品生成相关文章，拿来和本地文章进行比较打分。

6.当前搜索引擎是本地部署的searngx引擎，会整个Google， bing等主流搜索引擎结果并返回，搜索引擎并不部署在本端口，而是端口，和本系统处于同一个服务器中。

> **补充**：SearXNG 部署在同一台服务器（10.10.130.82）端口 **8080**，地址为 `http://10.10.130.82:8080`。newsfilter 部署在同一台服务器端口 **8000**，调用路径为 `http://10.10.130.82:8000/api/test/query`。两者均为独立常驻服务，不随本项目重启而受影响。

7.当前文档中说明的是需要同时生成SEO友好和GEO友好两种，但是同时生成会增加开销和时间，这个需要结合实际业务需求，看看到底是全部生成，还是做成可以选择的模块。

8.之前提到过插入图片的事情，插入图片这个模块目前默认只能插入本地图片，而且安排在文章最后。另外还有一个生成图片的功能，由于现在公司中转站不允许gpt调用Request请求，所以暂时无法实现，后续可以选择开放gpt。

9.当前管理模块和生成模块是混在一起的，后期上线的话可以开发成管理者和用户两个平台，把管理和生成模块分开。

10.当前模型使用的api key都在服务器上写着，到时候如果key过期需要更换成有效的。

> **补充**：API Key 在 `data/config.json` 的 `apiProfiles[].apiKey` 字段，通过前端设置页面可直接修改，无需 SSH 进服务器手动编辑文件。前端传回 `********` 时后端会保留原密钥，不会意外覆盖。

11.当前文档中的评价指标有些可能和业务不匹配，需要后期调整部分指标的评分。

> **补充**：评分规则（60 项 EEAT checklist 的权重和判断标准）通过 `prompts.zh.optimizer` 字段配置，可在前端设置页面直接修改 prompt 内容来调整评分侧重点，无需改代码。

12.当前成本核算主要结果是，大部分开销都是在entity抽取这个模块，因此可以在这个模块使用更便宜的LLM（Deepseek），而不是更贵的claude。

> **补充**：实测数据——完整生成一篇 4 章节博客（含 SEO+GEO 双版本 + 自动 1 轮迭代 + 评分），Claude claude-sonnet-4-6 模型约消耗 60,000 input + 20,400 output tokens，耗时约 6.5 分钟，成本约 0.29-0.56 元/篇。LLM 评分（evaluator）是最大耗时瓶颈，每次约 7,465 input tokens，约 28 秒。entity_extractor 换成 DeepSeek 后该步成本几乎可忽略不计。

13.实体抽取这个地方已经明确指明需要商品品牌这些信息，所以这些需要后面结合业务看看到底需不需要这些信息。

> **补充**：当前实体抽取 prompt 提取五类实体：products（具体产品/品牌/型号）、attributes（参数/规格/材质）、actions（操作步骤/使用方法）、problems（常见问题/痛点）、comparisons（对比对象/选择依据），每类最多 15 个。这套分类是按 SEO 内容缺口分析设计的，若业务更关注竞品对比或用户 FAQ，可直接调整 `prompts.zh.entity_extractor` 中的分类结构，无需改代码。
---

## 配置细节汇总表

以下为项目涉及的所有关键配置项，包含 API 密钥、模型、服务器信息和端点地址。

| 配置项 | 当前值 | 说明 |
|--------|--------|------|
| **服务器** | | |
| 服务器 IP | 10.10.130.82 | 内网地址 |
| SSH 用户 | root | |
| SSH 密码 | hongxuan | |
| 项目目录 | /root/ai-blog-studio | |
| 服务端口 | 4174 | 本项目 uvicorn 端口 |
| 线上地址 | http://10.10.130.82:4174 | |
| 本地地址 | http://127.0.0.1:4173 | run.py 启动 |
| **注意端口** | 8013 | 另一个进程，和本系统无关，已被占用 |
| **模型 API** | | |
| API 代理 Endpoint | https://claude.deeplumen.io | Anthropic 中转代理 |
| API Mode | anthropic_messages | |
| API Key | sk-9743aafed1c3e28dcebdee482b7fe3fcdb34945122aeb2c3e91dc5c1e69906f2 | deeplumen 中转 key |
| 授权 Header | Authorization: Bearer \{\{apiKey\}\} + anthropic-version: 2023-06-01 | headersJson 中配置 |
| 主模型（所有任务） | claude-sonnet-4-6 | 可选：claude-haiku-4-5-20251001 / claude-opus-4-6 |
| **实体抽取（建议单独配置）** | | |
| entity_extractor 任务 | deepseek-chat（已分配至 DeepSeek 卡片） | 约 1元/M 输入 + 2元/M 输出，比 Claude 便宜约 10 倍 |
| **搜索服务** | | |
| SearXNG 端点 | http://10.10.130.82:8080 | 同服务器独立常驻进程 |
| newsfilter 端点 | http://10.10.130.82:8000/api/test/query | 同服务器独立常驻进程 |
| 搜索最大结果数 | 20（前端显示）/ 80（entity分析） | maxResults / analysisMaxResults |
| 搜索超时 | 30 秒 | timeoutSeconds |
| 每词搜索页数 | 3 页 | pagesPerQuery |
| **GPTZero** | | |
| GPTZero 端点 | https://api.gptzero.me/v2/predict/text | |
| GPTZero API Key | 8a24eb826d164608a4d99eacfbed4cbc | |
| GPTZero 权重 | 0.35 | 在总分中的占比 |
| GPTZero 启用状态 | true | gptZeroSettings.enabled |
| **本地开发环境** | | |
|                              |                                                              |                                                   |
| 本地启动脚本 | start_local.bat / run.py | |
| 本地同步脚本 | push_to_server.ps1 | 含备份+SCP上传+重启 |
| **文件路径** | | |
| 配置文件 | data/config.json | 含 API Key，不要泄露 |
| 文章存储 | data/blogs/*.json | 用户资产，同步时不要删除 |
| 启动日志 | /root/ai-blog-studio/server.log | |
| PID 文件 | /root/ai-blog-studio/server.pid | |
| 备份目录 | /root/ai-blog-studio/backups/ | 每次 push 前自动打 tarball |


---

## 附录一：搜索引擎模块说明（SearXNG + newsfilter）

### 1. 整体架构

本项目的搜索能力以 SearXNG 作为数据抓取入口，结合本地排序算法对结果进行过滤与重排，两个组件均部署在同一台服务器（10.10.130.82），均为独立常驻服务，不随主项目重启而受影响：

- **SearXNG**（端口 8080）：开源元搜索引擎，聚合 Google、Bing 等多个主流搜索引擎，以 JSON 格式返回原始搜索结果
- **newsfilter**（端口 8000）：自研内容过滤服务，部署为可选外部重排端点（`rankerEndpoint`）；其核心算法逻辑（域权威评分、来源独立性、时间衰减、去重）已内置于主项目的 `reference_search.py`

主项目调用 `POST /api/search-references` 后，SearXNG 负责抓取原始候选，本地算法对候选进行过滤与重排，最终返回适合商品博客参考的高质量结果列表。

---

### 2. SearXNG 搜索逻辑（主项目侧，reference_search.py）

**搜索词规划**（`search_planner` 模型）：

调用语言模型从用户需求中规划 4-8 个搜索词（primaryQuery + queries 数组）和 3-6 个核心实体词（coreTerms）。规划约束：

- primaryQuery 只包含商品本体（productName/productType），不含 market、SEO 等修饰词
- 先给宽泛高召回词（仅含商品实体），再给细分长尾词（含规格/场景/对比/采购）
- 禁止把泛词（"最佳"、"推荐"、"review"、"SEO"等）作为 primaryQuery 或 coreTerms
- 禁止把材质词或纯属性词（便携、耐用）作为 coreTerms 独立项

**多页抓取**：

每个搜索词默认抓取 3 页（`pagesPerQuery=3`），每页约 10 条结果，单词最多拿 30 条原始候选，多词并发。若某查询首页无结果，自动跳过后续页。

**种子重试**：

若 SearXNG 第一轮查询结果为空，自动用宽泛变体词（productName / productType 的原始形式）重试一次，meta 中记录 `retry` 字段说明原因。

**本地排序过滤算法**（`algorithm_rerank_references`）：

```
score =
  max(0, 20 - source_rank) × 1.8    # 原始搜索排名加成
+ authority × 12                     # 域权威性加成（PRODUCT_DOMAIN_AUTHORITY 表）
+ independent × 2.5                  # 独立来源标志加成（同域首条）
+ relevance × 34                     # 相关性得分（最大权重）
+ min(base_score, 18)                # 原始搜索分数补充
+ domain_boost                       # 域名加权（domainWeights 配置项）
+ freshness × 4                      # 内容时效加分（时间衰减，最高 +4）
- repeat_probability × 6             # 重复概率惩罚
- language_penalty                   # 语言不匹配惩罚（最高 90 分）
- low_value_penalty                  # 低价值域名惩罚（36 分）
- url_quality_penalty                # 购物车/登录/结算页面惩罚（22 分）
```

过滤策略：`sourceRelevance < 0.06` 的结果被过滤掉（零相关性），若全部结果都被过滤，返回空列表。

**客户来源加权注入**：

`searchSettings.customerSources` 配置的指定 URL，以 `score = 10 + weight + relevance × 10` 插入候选列表参与最终排序。

---

### 3. newsfilter 服务说明

newsfilter 是独立的 FastAPI 服务（端口 8000，v2.2.0），以算法过滤为核心，不依赖外部 LLM。其核心设计理念已被主项目 `reference_search.py` 直接采用，作为内置排序算法运行，不需要额外的网络调用。

**核心算法组件：**

**① 域权威评分（PRODUCT_DOMAIN_AUTHORITY）**

按域名查预设权威权重表，覆盖 60+ 域名，针对商品/产品搜索场景标定：

| 类别 | 代表域名 | 权重范围 |
|------|---------|---------|
| CN 产品评测平台 | zhihu.com, sspai.com, smzdm.com | 0.68–0.72 |
| CN 数码/科技媒体 | 36kr.com, ithome.com, ifanr.com | 0.62–0.65 |
| CN 电商平台 | jd.com, tmall.com, taobao.com | 0.44–0.55 |
| CN 财经媒体 | yicai.com, caixin.com | 0.60 |
| EN 产品评测 | rtings.com, cnet.com, techradar.com | 0.71–0.74 |
| EN 科技媒体 | theverge.com, wired.com | 0.68–0.70 |
| 未收录域名 | — | 0.25（默认） |

子域名通过后缀匹配自动继承权重（如 `zhuanlan.zhihu.com` → 0.72）。

**② 来源独立性判断**

遍历所有候选结果，同一域名的首条结果标记 `isIndependent=True`，后续条目标记为 `False`。独立来源在排序时额外获得 +2.5 分，确保结果列表来源多元、不被单一域名刷屏。

**③ 内容时效衰减**

采用指数衰减公式：`freshness = exp(-λ × delta_days)`，其中 `λ=0.04`（商品内容半衰期约 17 天）。有发布日期的结果会根据内容新鲜度获得额外加分（最高 +4 分），无法解析日期的结果不加分也不扣分。

**④ URL 质量过滤**

识别并惩罚购物车、结算、登录、注册等低价值页面（`/cart`、`/checkout`、`/login` 等路径特征），直接扣 22 分，避免无内容的功能性页面出现在参考结果中。

---

### 4. 关键配置参数

| 参数 | 值 | 说明 |
|------|-----|------|
| SearXNG 端点 | http://10.10.130.82:8080 | 主搜索入口 |
| newsfilter 端点 | http://10.10.130.82:8000 | 可选外部重排端点（rankerEndpoint） |
| pagesPerQuery | 3 | 每个搜索词抓取页数（约 30 条/词） |
| PRODUCT_TIME_DECAY_LAMBDA | 0.04 | 时间衰减系数（商品内容半衰期 ~17 天） |
| sourceRelevance 阈值 | 0.06 | 低于此值的结果被过滤 |
| 低价值 URL 惩罚 | 22 分 | 购物车/登录/结算页面 |

---


## 附录二：SEO + GEO 内容自动生成模块规格（2026-05-26）

SEO + GEO 内容自动生成模块

以下内容来自文档 *SEO-GEO内容生成模块-0526-hertz.docx*  与 *双轨标题生成模块-MVP工程规格-0528.docx*，评分细则在 *EEAT-Checklist-全量-0527-Hertz.xlsx*





# 1. 文档目的：
## 1.1 背景
我们的SEO工具进入第二期。当前市面上的AI内容生成工具普遍停留在“喂关键词出长文”的阶段，在2026年的算法环境下，Google已部署低熵内容过滤器、AI指纹识别和信息增益评分，传统的“调用大模型API+模板”方式不仅排名收益锐减，还可能触发降权（因为不提供信息增量，无法打破数学模型趋于平庸的平均值的机制，检索系统无法负熵）。与此同时，生成式搜索引擎的引用机制进一步把流量分配权交给了“可被结构化抽取”和“具备独有信息”的页面。客户对“一站式生产SEO+GEO双友好内容”的诉求强烈，Deeplumen在SEO的旧世界需要面对高楼林立的竞对，长期的品牌公信力和用户习惯已经锁死用户，只是提供SEO的价值，很难在竞争中赢得身位，在搜索范式转移的窗口期，提供GEO的新叙事，可以拉齐跟竞对的身位，甚至在这个充满焦虑的叙事中，提供颠覆的力量。
## 1.2 目标
为客户提供端到端的内容自动生成能力：输入关键词或主题，输出可直接发布、对SEO与GEO均友好的结构化页面草稿。
底层逻辑采用“SERP前10解析 → 信息增益识别 → 缺口补齐 / 增益创作”的差异化策略，避免与SERP现存内容同质化。
内置反低熵Prompt编排、Schema自动注入、DOM结构优化，使产出内容在Google正常索引、AI引擎可被引用。
## 1.3 术语表

# 2. 产品定位与价值主张
## 2.1 用户痛点
根据之前调研shopify客户用户画像（降低知识门槛，提供傻瓜式优化功能）当前的工作流痛点集中在三处：
AIGC直接写出来的内容“一眼AI”，机味太浓，且如果都是大语言模型生产的内容，不提供信息增量，无法打破数学模型趋于平庸的平均值的机制，检索系统无法负熵。导致Google索引但不排名，AI引擎引用率低。
人工分析SERP前10太慢，一个关键词簇要花一个内容运营3-5天，无法规模化。
Schema、内链、E-E-A-T信号需要工程介入，内容上线后还要再返工。
## 2.2 解决方案概述
本模块把“SEO + 内容编辑 + 前端工程师”的串行链路压缩成一条自动化流水线。客户输入种子关键词或URL，系统在小时级内输出：
一份SERP情报报告（前10内容的实体覆盖矩阵、信息密度评分、共同语义缺口清单）。
一组围绕该主题的内容草稿（每篇明确指明本篇相对SERP贡献的信息增益点）。
可直接渲染的HTML + JSON-LD Schema，开箱即用。
一份内容质量审计报告（低熵评分、E-E-A-T信号）。
备注：审计报告实现方案：
低熵评分/AI指纹检测
现成解决方案
GPTZero：$0.01/次（按 50K 字符），文档清晰，1 小时能接完。准确率主流但在中文上偏弱。最便宜的成熟选择。
Originality.ai：$0.01/1000 字，SEO 圈用得最多，对 GPT 系输出特别敏感。中文支持比 GPTZero 好一点。按 token 计费比按次划算。
Sapling AI Detection：免费 tier 含 50 次/月，付费 $25/月起，做对照很合适。
自部署开源
Binoculars：用两个小语言模型计算 cross-perplexity 比值。论文级准确率，单卡 GPU 一天能跑几千篇。整体几乎零成本，是开源里目前最强的方案。
EEAT信号检测
规则化方案最为经济且准确
自研最小实现（最推荐）
写一份 60 项的 checklist，分四象限打分，每项 0/0.5/1。用 BeautifulSoup + spaCy + 几个 regex 就能跑：
Experience（10 项）：第一人称体验段落（"在我们测试中"、"我尝试了"）、原创图片（图片 hash 比对 Shutterstock/Unsplash 公开 hash 库）、具体测试场景的数值、产品/设备型号的具体提及
Expertise（15 项）：作者署名 + Bio 段落、Schema.org Person 块（sameAs 指向 LinkedIn/学术页）、领域术语密度（用客户提供的术语表统计）、外部权威引用计数
Authoritativeness（15 项）：发布日期 + 更新日期、引用数（外链到 .edu / .gov / wikipedia / 行业头部站）、品牌一致性信号（Logo + Schema Organization）
Trustworthiness（20 项）：HTTPS、Contact/Privacy/Terms 页面存在、免责声明（医疗/金融场景）、Schema 与正文一致性、author byline 链接到 /author/ 页面软信号（如"这一段读起来像真实经验吗"）用 GPT-4o-mini 做二分类，单次 $0.001。
总成本：每篇 < $0.005，开发 3-5 个工作日。

# 3. 核心策略框架
## 3.1 SEO + GEO 双优化目标
模块产出必须同时满足两类“读者”——Google传统索引爬虫与AI生成引擎的检索代理。两者关心的指标存在差异，但都对低检索成本+ 高信息增益”的页面给出更高权重，MVP工程围绕自动双效的策略展开。
## 3.2 信息增益驱动的内容生产逻辑
我们的核心生产假设是：算法已经把“与SERP内容相似度高的新页面”归为冗余，索引但不排名；只有提供独有信息（新数据、新视角、新实体覆盖）的页面，才会被分配流量与AI引用位。因此模块A的输出（缺口清单）是后续所有生成步骤的“立项依据”，不允许越过此步骤直接生成。
## 3.3 端到端流程
用户在前端配置输入 → 提交任务。
后端跑流水线：抓 SERP → 抽实体 → 找缺口 → 生成内容 → 加 Schema → 质量审计。
流水线产物（？）写入对象存储。
前端轮询任务状态，展示预览 +编辑+ 推送。
# 4. 三个核心模块
## 4.1 模块 1：SERP 缺口识别
职责：抓 SERP 前 10 → 实体抽取 → 找出共同未覆盖的实体清单。
### 实现方式（具体到能开工）
调 SerpAPI 或 DataforSEO 拉关键词的 SERP，取前 10 个 organic 结果的 URL、标题、Meta。
用 trafilatura 抓每个 URL 的正文（一次失败放弃该 URL，不重试）。
把每篇正文喂给 GPT-4o-mini 提取实体列表，prompt 模板见附录 A，返回结构化 JSON。
聚合 10 篇结果的实体，统计每个实体出现的覆盖文档数。
把覆盖文档数 < 3 的实体标记为「缺口」。再合并 SerpAPI 返回的 PAA（People Also Ask）问题作为补充缺口。
附录A：实体抽取模版
你将看到一篇关于 {  } 的网页正文。请抽取其中提到的所有具体实体，按以下分类返回 JSON:
{
  "entities": {
    "products": [...],         // 具体产品 / 品牌 / 型号
    "attributes": [...],       // 参数 / 规格 / 材质
    "actions": [...],          // 操作步骤 / 使用方法
    "problems": [...],         // 常见问题 / 痛点
    "comparisons": [...]       // 对比对象 / 选择依据
  }
}
约束:
- 实体必须是文中明确出现的，不要泛化推断。
- 每类最多 15 个，去重。
- 中文与英文混合时统一返回原文形式。
## 4.2 模块 2：受约束的内容生成
职责：基于模块 1 的缺口清单，生成结构化草稿。
### 实现方式：
加载 Prompt 模板（按内容类型 Article / FAQ / How-To 各一套，见附录 B）。
把缺口清单、PAA 问题、用户粘贴的「额外要点」作为变量注入 Prompt。
反低熵词汇黑名单（约 30 个高频词，见附录 C，可拓展）作为系统级约束注入。
调 GPT-4o 或 Claude Sonnet，一次请求生成整篇大纲 + 各段落正文。
生成完后做后处理：扫描黑名单词汇，命中则用 LLM 的 second-pass 改写该句；对每段做 SimHash 与 SERP 段落比对，命中近重复（SimHash 距离 < 8）则重生成该段一次。
附录 B：内容生成 Prompt 模板（Article 类型示例）
你是一名 {industry} 领域的资深内容编辑，正在为 {keyword} 撰写一篇深度文章。

【SERP 现状】
前 10 名竞品文章已覆盖的角度：{covered_entities}
他们共同遗漏的实体与子问题：{gap_entities}
用户在 PAA 中提出的问题：{paa_questions}

【独有信息】
(以下由用户提供，可能为空)
{user_extra_points}

【写作约束】
- 围绕 gap_entities 与 paa_questions 组织正文，覆盖率不低于 80%。
- 字数 1200-2000 字，分 3-5 个 H2，每个 H2 下 2-4 个 不超过 120 字的段落。
- 严禁出现以下词汇：{blacklist}。
- 首段必须以具体事实、数值或场景开头，不允许概括陈述。
- 文末输出一段 80-120 字的 Wiki 体结论摘要，供 AI 引擎抽取。

请直接输出 Markdown，无需解释。
附录 C：反低熵词汇黑名单（MVP 阶段固定 30 词，可拓展）

### MVP 验收口径
生成内容长度 1200-2000 字（Article 类型）。
AI 指纹分（GPTZero） ≤ 35%。
黑名单词汇出现率 = 0。
段落与 SERP 的 SimHash 距离 ≥ 8（无近重复）。
## 4.3 模块 3：Schema 注入与质量审计
职责：给草稿加上结构化数据，跑一遍审计，产出最终交付物。
### 实现方式
根据内容类型选 Schema 模板：Article / FAQPage / HowTo（共 3 个模板，硬编码）。
从草稿正文里抽取 Schema 必填字段（headline、author、datePublished、articleBody 等）。author 默认填用户租户名。
生成 JSON-LD，跑一次 schema.org 本地语法校验。
可选：调 Google Rich Results Test API 做远程校验（额度有限时降级为只做本地校验）。
生成质量报告 .md：AI 指纹分、与 SERP 的 SimHash 最近距离、缺口覆盖率、字数统计。
### MVP 验收口径
schema.org 本地校验通过率 = 100%（不通过的不允许进入交付包）。
Google Rich Results Test 通过率 ≥ 90%（远程校验时）。
# 5. 风险与开放问题
## 5.1 风险
Google算法在2026年继续迭代，AI指纹检测口径可能变化，需保持月级版本更新。

信息增益评分依赖实体抽取精度，长尾、新兴行业的本体覆盖不足时分数会失真。



---

## 附录三：双轨标题生成模块 MVP 工程规格（2026-05-28）

双轨标题生成模块
# 为什么要做双轨
SEO 与 GEO 对「什么是好标题」的判断标准不同，硬要一个标题同时满足两种引擎，结果是两边都不够好。正文没有如此设计的原因是标题公约数小，正文容错率大（字数多，空间大，可以实现双效）。

## 设计原则
一次调用产出两套候选：节省成本与延迟，模型在同一上下文中能确保两套版本明显差异化。
结构化输出：用 response_format JSON object 强约束输出格式。
每套候选 ≥ 3 个：方便后续评分阶段过滤掉低分项。
显式禁用同质化：Prompt 中要求两套候选必须在句式、修辞、信息侧重上有实质差异。
## System Prompt（硬编码）
You are an SEO + GEO title strategist. Your task is to produce TWO sets of title
candidates for the same content:

1. SEO TITLE SET — optimized for Google SERP click-through and ranking.
   Characteristics:
   - Noun-phrase or question form, with the main keyword in the first 8 characters
     (Chinese) or first 4 words (English)
   - Uses click-through hooks: specific numbers, current year, comparative words
     ("vs", "对比"), superlative qualifiers ("最佳", "完整", "实测"),
     or bracketed annotations
   - Length: 14-28 Chinese characters, or 50-65 English characters
   - May append brand name with " | " or " - " separator if brand_name is provided
     and seo_append_brand=true

2. GEO TITLE SET — optimized for AI search engine citation and extraction
   (Perplexity, ChatGPT Search, AI Overviews, Claude).
   Characteristics:
   - Complete statement or precise question form. Self-contained: comprehensible
     without context
   - High entity density: at least 2 named entities or specific numerical parameters
   - No click-through hooks ("最佳", "完整指南", "you must know") — AI engines
     down-weight these
   - Length: 16-32 Chinese characters, or 60-80 English characters
   - The first content word should be a concrete noun or named entity, NOT a
     generic qualifier

THREE ABSOLUTE RULES:

R1. Both sets must include the main keyword (or its near-synonym), but the SEO set
    requires keyword-first position while the GEO set does not.

R2. The two sets must differ in surface form, NOT just by rearranging the same words.
    A reader should be able to tell at a glance which one is SEO-focused and which
    is GEO-focused.

R3. Neither set may use a title that has high lexical overlap (>50% token overlap)
    with any of the provided SERP_TOP_TITLES. Differentiation against existing SERP
    is a hard requirement.

VOICE CALIBRATION:
- SEO titles: persuasive but factual. Avoid pure clickbait. Use specific numbers
  and named entities even within the persuasive frame.
- GEO titles: neutral, encyclopedic tone. Avoid first-person, avoid imperatives,
  avoid promotional adjectives.

OUTPUT DISCIPLINE:
- Return ONLY a JSON object matching the schema below. No commentary, no markdown.
- Each set contains exactly 3 candidates, ordered by your confidence.
## Task Prompt（运行时填充变量）
TASK: Generate two title sets for the keyword "{keyword}" in {locale} for
{content_type} content targeting {audience_profile}.

============================================================
[A] SERP CONTEXT — what already exists, you must differentiate
============================================================

Existing top-10 SERP titles (DO NOT mirror these):
{serp_top_titles}

Information gaps you should hint at (titles that promise to address these will
outperform):
{gap_entities_brief}

PAA (People Also Ask) questions Google surfaces around this keyword:
{paa_questions}

============================================================
[B] BRAND CONFIG
============================================================

Brand name: {brand_name_or_none}
SEO append brand: {seo_append_brand}

If a brand is provided and seo_append_brand is true, the SEO set MUST append
"| <brand_name>" or " - <brand_name>" to ALL 3 SEO candidates.
The GEO set MUST NOT include the brand.

============================================================
[C] LENGTH BOUNDS (strict)
============================================================

Locale: {locale}

For zh-CN:
  SEO: 14-28 Chinese characters per candidate (after brand suffix)
  GEO: 16-32 Chinese characters per candidate

For en-US:
  SEO: 50-65 characters per candidate (after brand suffix)
  GEO: 60-80 characters per candidate

Candidates outside these bounds will be rejected.

============================================================
[D] DIFFERENTIATION REQUIREMENTS
============================================================

All 3 candidates within each set must differ from each other in at least one of:
syntactic structure, entity emphasis, or modifier strategy.

The SEO set's best candidate and the GEO set's best candidate must be
substantively different ideas — not just rephrasing.

============================================================
[E] OUTPUT SCHEMA (exact)
============================================================

{
  "seo_candidates": ["...", "...", "..."],
  "geo_candidates": ["...", "...", "..."],
  "rationale": {
    "seo_hooks_used": ["数字" | "年份" | "对比" | "实测" | "排名" | ...],
    "geo_entities_used": ["entity 1", "entity 2", ...],
    "key_differentiation_axis": "<one-sentence description>"
  }
}

Return ONLY this JSON.
## 评分项与实现
总分 = 6 项的平均值（满分 1.0）。
## 关键评分函数
import re
import jieba
from simhash import Simhash

CONTEXT_DEPENDENT_PREFIXES = [
    "为什么", "怎么", "如何看待", "上文", "前面提到",
    "本期", "这一篇", "继上次", "Why", "How to view"
]
SEO_HOOKS = ["最佳", "推荐", "完整", "实测", "对比", "vs", "排名",
             "指南", "Best", "Top", "Complete", "Ultimate", "Review"]

def score_title(title: str, ctx: dict) -> dict:
    """
    ctx = {
        "keyword": str,
        "locale": "zh-CN" | "en-US",
        "serp_titles": list[str],
        "track": "seo" | "geo",
    }
    """
    scores = {}

    # ---- 1.1 唯一性（SimHash 距离）----
    title_hash = Simhash(_features(title, ctx["locale"]))
    min_dist = min(
        title_hash.distance(Simhash(_features(t, ctx["locale"])))
        for t in ctx["serp_titles"]
    ) if ctx["serp_titles"] else 64
    scores["1.1_uniqueness"] = 1.0 if min_dist >= 12 else (0.5 if min_dist >= 8 else 0)
    
    # ---- 1.2 含主关键字 ----
    if ctx["keyword"] not in title:
        scores["1.2_keyword"] = 0
    else:
        pos = title.find(ctx["keyword"])
        if ctx["track"] == "seo":
            if pos / len(title) <= 0.33:
                scores["1.2_keyword"] = 1.0
            elif pos / len(title) <= 0.5:
                scores["1.2_keyword"] = 0.7
            else:
                scores["1.2_keyword"] = 0.4
        else:
            scores["1.2_keyword"] = 1.0
        density = len(ctx["keyword"]) / len(title)
        if density > 0.5:
            scores["1.2_keyword"] *= 0.5
    
    # ---- 1.4 长度合规 ----
    L = len(title)
    if ctx["locale"] == "zh-CN":
        bounds = (14, 28) if ctx["track"] == "seo" else (16, 32)
    else:
        bounds = (50, 65) if ctx["track"] == "seo" else (60, 80)
    if bounds[0] <= L <= bounds[1]:
        scores["1.4_length"] = 1.0
    elif bounds[0] - 3 <= L <= bounds[1] + 3:
        scores["1.4_length"] = 0.7
    else:
        scores["1.4_length"] = 0.3
    
    # ---- 1.6 实体密度 ----
    entities = _extract_entities(title, ctx["locale"])
    extra = [e for e in entities if e != ctx["keyword"]]
    if ctx["track"] == "geo":
        scores["1.6_entity_density"] = 1.0 if len(extra) >= 2 else (0.5 if extra else 0)
    else:
        scores["1.6_entity_density"] = 1.0 if extra else 0.5
    
    # ---- 1.7 自含性 ----
    has_dep = any(title.startswith(p) for p in CONTEXT_DEPENDENT_PREFIXES)
    entity_ratio = sum(len(e) for e in entities) / len(title)
    if has_dep:
        scores["1.7_standalone"] = 0.3
    elif entity_ratio >= 0.6:
        scores["1.7_standalone"] = 1.0
    elif entity_ratio >= 0.4:
        scores["1.7_standalone"] = 0.7
    else:
        scores["1.7_standalone"] = 0.4
    
    # ---- 1.3 语义质量（LLM judge）----
    scores["1.3_semantic"] = _llm_semantic_judge(title, ctx)
    
    scores["total"] = sum(scores.values()) / 6
    return scores
## 语义质量的 LLM 评价
给定标题 "{title}" 与关键词 "{keyword}"，以及目标轨道 {track}。
评估三项，每项 0/0.5/1：

A. 概括度：标题对内容核心结论的概括程度
B. 新意度：相对同类标题 "{serp_titles}"，本标题是否提供差异化角度
C. 引用价值（track=geo）/ CTR 钩子（track=seo）：
   - GEO: 把标题作为查询提交给 AI 引擎时，是否清晰指向某个具体可被引用的事实
   - SEO: 标题是否含有效的点击诱因（数字、对比、年份、限定）

返回 JSON: {"A": 0|0.5|1, "B": 0|0.5|1, "C": 0|0.5|1, "total": A/3+B/3+C/3, "reason": "..."}
用 GPT-4o-mini，单次约 $0.001。6 个候选共约 $0.006。

# 选择策略
候选打分完成后的处理流程：
def select_titles(seo_candidates, geo_candidates, ctx):
    # 1. 硬过滤：1.1=0 或 1.2=0 或 1.4<0.5 的候选丢弃
    seo_filtered = [c for c in seo_candidates
                    if c.scores["1.1_uniqueness"] > 0
                    and c.scores["1.2_keyword"] > 0
                    and c.scores["1.4_length"] >= 0.5]
    geo_filtered = [c for c in geo_candidates
                    if c.scores["1.1_uniqueness"] > 0
                    and c.scores["1.2_keyword"] > 0
                    and c.scores["1.4_length"] >= 0.5]

    # 2. 兜底：如果某一轨过滤后为空，触发 1 次重生成
    if not seo_filtered or not geo_filtered:
        return regenerate_once(ctx)
    
    # 3. 按总分排序
    seo_filtered.sort(key=lambda c: c.scores["total"], reverse=True)
    geo_filtered.sort(key=lambda c: c.scores["total"], reverse=True)
    
    # 4. 同标题去重：如果 SEO 推荐 == GEO 推荐，让 GEO 退回第 2 名
    if seo_filtered[0].title == geo_filtered[0].title and len(geo_filtered) > 1:
        geo_recommended = geo_filtered[1]
    else:
        geo_recommended = geo_filtered[0]
    
    return {
        "seo": {
            "recommended": seo_filtered[0].title,
            "alternatives": [c.title for c in seo_filtered[1:3]],
            "scores": seo_filtered[0].scores,
        },
        "geo": {
            "recommended": geo_recommended.title,
            "alternatives": [c.title for c in geo_filtered[:3]
                              if c != geo_recommended][:2],
            "scores": geo_recommended.scores,
        },
        "strategy_note": _build_strategy_note(seo_filtered[0], geo_recommended),
    }

# 工程实现要点
## 数据流（最小化设计）
[输入] keyword + locale + content_type + brand + 模块1产出
   ↓
[1] 调 GPT-4o 一次 → 拿到 seo_candidates × 3 + geo_candidates × 3
   ↓
[2] 对每个候选并行评分（6 项，~2 秒）
   ↓
[3] 硬过滤 → 排序 → 选择推荐 + 备选
   ↓
[4] 生成 strategy_note
   ↓
[输出] JSON 结果

# UI/UX 建议（前端）
MVP 阶段最简界面：
┌──────────────────────────────────────────────────────────┐
│ 标题生成结果                                              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  [ SEO 推荐 ]              [ GEO 推荐 ]                   │
│  ┌──────────────────┐      ┌──────────────────┐          │
│  │ 2026年最佳意式磨豆│      │ 锥形磨芯意式磨豆机│          │
│  │ 机推荐：锥形磨芯..│      │ 的研磨均匀度：60..│          │
│  │                  │      │                  │          │
│  │ 得分: 0.93       │      │ 得分: 0.97       │          │
│  │ 长度: 32字       │      │ 长度: 34字       │          │
│  │ 实体: 3 / 钩子: 3│      │ 实体: 4          │          │
│  └──────────────────┘      └──────────────────┘          │
│   [选择此版本]              [选择此版本]                  │
│                                                          │
│  ┌────────────────────────────────────────────┐          │
│  │ 策略建议：两个版本差异显著，建议同时采用：  │          │
│  │   - HTML <title> 用 SEO 版本               │          │
│  │   - H1 + Schema.headline 用 GEO 版本       │          │
│  │   [同时采用两个版本]                        │          │
│  └────────────────────────────────────────────┘          │
│                                                          │
│  ▼ 备选 2 个 SEO 候选                                     │
│  ▼ 备选 2 个 GEO 候选                                     │
│  ▼ 详细评分（点击展开）                                   │
└──────────────────────────────────────────────────────────┘
三个交互动作：
单选 SEO 版本
单选 GEO 版本
同时采用两个版本（即「双锚点」策略）



# 附录 A：SEO 钩子词库（MVP 内置）
中文：
最佳 / 推荐 / 完整 / 终极 / 全面 / 实测 / 对比 / 排名 / 指南 / 选购 / 评测 / 测评 / 综合 / 深度
英文：
Best / Top / Ultimate / Complete / Definitive / Comprehensive / Review / vs / Comparison / Guide / Tested
这些词允许出现在 SEO 候选标题中，但在 GEO 候选中是禁用项（命中即扣 1.7 自含性分）。
# 附录 B：GEO 自含性黑名单（MVP 内置）
标题开头出现以下词汇即扣 1.7 分至 0.3：
中文：
为什么 / 怎么 / 如何 / 上面 / 前面 / 上文 / 这一篇 / 本文 / 接下来
英文：
Why / How / The above / In this / Continuing from / Following up
