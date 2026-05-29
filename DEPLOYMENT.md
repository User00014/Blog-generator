# AI Blog 自动生成工具部署说明

更新时间：2026-05-21

## 本地项目

本地目录：

```text
C:\Users\13488\Desktop\工作\Blog生成
```

本地启动方式：

```text
双击 start_local.bat
```

启动器功能：

- `1. Start`：启动本地服务
- `2. Check status`：检查服务状态
- `3. Stop`：停止本地服务
- `4. Restart`：重启本地服务
- `5. Exit`：退出启动器

本地默认地址：

```text
http://127.0.0.1:4173
```

本地 Python 优先使用：

```text
E:\anaconda\envs\envb\python.exe
```

## 服务器部署

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

注意：服务器上 `8013` 是其他工具端口，部署本项目时不要占用或停止它。

## 系统结构

当前应用是 FastAPI + 静态前端：

```text
backend/main.py                 FastAPI 路由入口
backend/services/generator.py   大纲、正文、内容迭代、分段生成逻辑
backend/services/model_client.py OpenAI-compatible / Claude / Gemini 调用层
backend/services/reference_search.py 联网参考搜索、Top 排序、生图占位接口
backend/services/storage.py     本地配置和文章 JSON 持久化
public/index.html               单页前端结构
public/app.js                   前端交互逻辑
public/styles.css               前端样式
data/config.json                API 卡片、模型任务分配、Prompt、搜索服务配置
data/blogs/                     生成文章和版本 JSON
```

生成链路：

```text
需求输入 -> 联网参考 -> 意图分析/主题选择 -> 大纲确认 -> 分段正文生成 -> 文章库保存
```

内容迭代链路：

```text
选择/输入文章 -> 评价 AI 打分建议 -> 修改 AI 分段改写正文 -> 每轮结果可保存为版本
```

## 外部依赖

模型调用：

```text
Claude / OpenAI-compatible API 配置保存在 data/config.json
当前默认模式：anthropic_messages
当前模型：claude-sonnet-4-6
```

搜索依赖：

```text
newsfilterEndpoint: http://10.10.130.82:8000/api/test/query
searxngEndpoint:    http://10.10.130.82:8080
默认 maxResults:    15
默认 timeoutSeconds: 25
```

说明：

- `/api/search-references` 会优先请求 `newsfilterEndpoint`。
- 如果 `newsfilter` 没启动或连接失败，会自动降级到 SearXNG。
- 当前部署验证时 `newsfilter` 未启动，SearXNG 可用。
- 搜索结果会归一化为卡片字段：标题、URL、域名、摘要、缩略图、权重分数、排名。
- 前端支持分别勾选“引用链接”和“样式参考”。

图片能力：

```text
/api/generate-image
```

当前只是占位接口，返回 `pending_provider`。等生图模型调试好后，在 `backend/services/reference_search.py` 的 `generate_image_placeholder` 中接入真实模型即可。上传图片目前会按 Markdown 章节位置插入，不再统一放文末。

## 服务器启动命令

服务器依赖目前放在项目内的 `vendor` 目录，启动时需要设置 `PYTHONPATH`：

```bash
cd /root/ai-blog-studio
PYTHONPATH=/root/ai-blog-studio/vendor nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 4174 > server.log 2>&1 &
echo $! > server.pid
```

## 服务器停止命令

优先使用 `server.pid`：

```bash
cd /root/ai-blog-studio
if [ -f server.pid ]; then
  kill "$(cat server.pid)" || true
  rm -f server.pid
fi
```

如果 pid 文件失效，可按端口查找：

```bash
ss -ltnp | grep ':4174'
```

只停止本项目的 `4174` 进程，不要处理 `8013`。

## 服务器重启命令

```bash
cd /root/ai-blog-studio
if [ -f server.pid ]; then
  kill "$(cat server.pid)" || true
  rm -f server.pid
fi
old=$(ss -ltnp 2>/dev/null | grep ':4174' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -n 1)
if [ -n "$old" ]; then
  kill "$old" || true
fi
PYTHONPATH=/root/ai-blog-studio/vendor nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 4174 > server.log 2>&1 &
echo $! > server.pid
```

## 部署同步范围

本地修改完成并测试后，再同步到服务器。

通常需要同步：

```text
backend/
public/
data/config.json
data/blogs/
run.py
requirements.txt
README.md
start_local.bat
.gitignore
DEPLOYMENT.md
```

说明：

- `data/config.json` 保存 API 卡片、任务分配、语言、prompt 和搜索服务配置。
- `data/blogs/` 是文章库数据。除非明确要同步文章，否则不要做删除式同步。
- API Key 不应打印到日志或写入部署说明；配置文件同步即可。
- 同步前建议备份服务器当前版本。
- 同步 `data/blogs/` 时不要做删除式同步，避免误删服务器已有文章。

## 重要接口

基础：

```text
GET  /api/config
PUT  /api/config
GET  /api/blogs
GET  /api/blogs/{id}
POST /api/blogs
PUT  /api/blogs/{id}
DELETE /api/blogs/{id}
```

生成：

```text
POST /api/search-references      联网搜索 Top 参考文章
POST /api/intent-analysis        根据需求和搜索结果分析写作意图
POST /api/outline                生成大纲
POST /api/generate               普通正文生成
POST /api/generate/stream        流式分段正文生成，前端默认使用
POST /api/generate-image         图片生成占位接口
```

迭代：

```text
POST /api/score
POST /api/score/compare
POST /api/adversarial-train
POST /api/adversarial-train/stream
```

API 检测：

```text
POST /api/test-profile
```

## 低消耗验证命令

服务器上可用：

```bash
curl -sS http://127.0.0.1:4174/api/config | head
curl -sS http://127.0.0.1:4174/assets/app.js | grep -q searchReferences && echo ok
curl -sS http://127.0.0.1:4174/assets/styles.css | grep -q referenceCards && echo ok
```

搜索接口低消耗测试：

```bash
curl -sS -X POST http://127.0.0.1:4174/api/search-references \
  -H 'Content-Type: application/json' \
  -d '{"language":"zh","productType":"便携手冲咖啡壶","market":"中国","promotionGoal":"AI检索曝光","maxResults":3}'
```

图片占位接口：

```bash
curl -sS -X POST http://127.0.0.1:4174/api/generate-image \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"server ping image"}'
```

端口检查：

```bash
ss -ltnp | grep -E ':(4174|8013) '
```

预期：

```text
4174 是本项目
8013 是其他工具，不要停止或占用
```

## 当前部署记录

最近一次部署：

```text
2026-05-20
```

部署目标：

```text
/root/ai-blog-studio
```

服务端口：

```text
4174
```

本次变更：

```text
评分模块改为按 EEAT-Checklist-全量-0527-Hertz.xlsx 的 60 项 E-E-A-T 指标执行。
表格规则已导出到 data/eeat_scoring_rules.json，后端会按象限权重重新计算最终分，不依赖模型自报总分。
评分 AI / 迭代评价 AI 必须返回全部 60 项 itemScores，每项只允许 0、0.5、1。
权重来源于表格“评分规则”子表，支持不同内容类型权重；阻断项为 T1、T9、T15、T20、A1。
前端评分展示新增 E/E/A/T 四象限分、GPTZero/大模型/综合分和阻断项提示。
评分现为“规则优先 + 大模型补充”：后端先对可稳定判断的指标执行 regex、URL、JSON-LD、外链、日期、关键词密度等规则检测，规则项 locked 后覆盖模型结果；模型主要补充故事性、感官细节、反方观点等难以稳定规则化的指标。
前端评分区会显示规则锁定项数量和模型补充项数量。
长文正文生成改为按大纲章节分段请求；内容迭代改写改为按 Markdown 章节分段请求，降低上游 HTTP 524 超时概率。
生成正文新增流式进度接口；前端进度条显示当前正文段落，迭代进度条显示当前轮次和改写段落。
生成流程新增“联网参考”步骤：需求 -> 联网参考 -> 大纲 -> 正文。
新增 /api/search-references，优先适配 newsfilter 接口，失败时降级到 SearXNG，并做 Top 15 加权排序。
参考卡片支持“引用链接”和“样式参考”多选，选择内容会进入大纲和正文生成上下文。
图片能力新增生图占位接口 /api/generate-image；上传图片改为按章节位置插入，不再统一放到文末。
文章库新增 Markdown / HTML 手动导入；HTML 会先在前端解析成 Markdown 再保存，保存文章、导入文章和全局设置保存都会弹窗反馈。
内容迭代模块新增“评分比较”：选择多篇文章，只调用评价 AI 分别打分，并输出平均分、最佳文章和总点评。
```

服务器备份文件：

```text
/root/ai-blog-studio/backups/pre_deploy_20260520_175857.tar.gz
```

部署后验证：

```text
http://127.0.0.1:4174/api/config
http://127.0.0.1:4174/
```

验证结果：

```text
/api/config 正常返回
首页正常返回
API profiles 数量：1
语言：zh
前端 JS 包含 searchReferences
前端 CSS 包含 referenceCards / imagePlanGrid
/api/search-references 正常返回搜索结果，当前 newsfilter 未启动但 SearXNG 降级可用
/api/generate-image 返回 pending_provider
8013 端口仍正常监听，未被本项目占用
```

## 交接注意事项

- 修改流程：先本地改、测试，通过后再上传服务器。
- 不要在服务器上直接改代码，避免本地和服务器版本不一致。
- 上传前先备份服务器目录。
- 不要覆盖或删除 `data/blogs/`，除非明确要迁移文章库。
- `data/config.json` 含 API Key，交接时只说明位置，不要把密钥写进文档或聊天记录。
- `newsfilter` 是独立项目，当前本应用只通过 HTTP 接口调用它，不强依赖它运行；它不可用时会走 SearXNG。
- 生图目前是占位接口，前端入口已做好，真实模型接入点在 `backend/services/reference_search.py`。
- 评分规则源文件是本地 `EEAT-Checklist-全量-0527-Hertz.xlsx`；线上运行读取 `data/eeat_scoring_rules.json`。
- 如果表格规则更新，先在本地重新导出 JSON、跑编译和评分计算测试，再上传服务器。
- 规则评分实现位置：`backend/services/generator.py` 的 `evaluate_eeat_rules`、`apply_rule_scores`、`calculate_eeat_report`。

## 工作约定

- 以后有修改时，先在本地修改并测试。
- 本地确认没问题后，再同步到服务器。
- 不在服务器上直接改代码。
- 不修改服务器系统环境变量、系统配置或关键系统文件。
- 服务器密码、API Key 等敏感信息不要写入 Markdown 文档。
