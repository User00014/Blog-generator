# 本地 AI Blog Studio

一个基于 FastAPI 的本地网页工具，用于生成面向 AI 检索曝光的电商 Blog。前端只负责输入和展示，大纲生成、正文生成、训练优化、配置和文章存储都在 Python 后端完成。

## 运行

优先使用 E 盘 Anaconda 的 envb 环境：

```powershell
cd "C:\Users\13488\Desktop\工作\Blog生成"
& "E:\anaconda\envs\envb\python.exe" run.py
```

打开：

```text
http://127.0.0.1:4173
```

## 项目结构

```text
backend/
  main.py                 FastAPI 路由和静态页面服务
  settings.py             路径和默认配置
  services/
    model_client.py       多 API 卡片和任务模型调用
    generator.py          大纲、正文、训练优化编排
    storage.py            配置和文章本地存储
public/
  index.html              前端页面
  app.js                  前端交互与 API 调用
  styles.css              卡片式工作台样式
data/
  config.json             API、模型和 prompt 配置
  blogs/                  生成文章 JSON
```

## API 行为

未配置 API 卡片、未给任务分配 API、缺 endpoint、API Key 或模型名时，后端会直接报错，不会使用 mock 或固定规则生成。

网页现在是竖向流程：

1. 输入需求和商品资料。
2. 调用“大纲生成”模型生成结构化大纲，用户可编辑确认。
3. 调用“正文生成”和“训练优化”模型生成最终 Markdown。
4. 在本地文章库检索、打开和删除结果。

语言选择只有中文和英文，界面始终为中文，语言只影响对应 prompt 和模型输出。
