# 医疗问诊项目

这是一个基于 LangGraph 的 Web 版医疗问诊项目。系统围绕一个标准状态图运行，覆盖以下核心能力：

- 医疗问题理解
- 风险分级
- 联网搜索
- 搜索失败后的查询重写
- 搜索失败后的保守回退回答
- Web 页面展示
- LangGraph 静态图展示
- 单次执行流程调试可视化

## 启动方式

```
1、创建一个.env，配置好以下参数
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL_NAME=
2、python run_api.py
```

启动后访问：

- 首页：`http://127.0.0.1:8000/`
- 接口文档：`http://127.0.0.1:8000/docs`
- 静态图源码：`http://127.0.0.1:8000/api/graph`

## Web 页面可以展示什么

首页会展示三部分内容：

1. 问诊输入区  
输入用户问题和 `thread_id`

2. 问诊结果区  
显示风险等级、意图总结、搜索词、搜索次数、最终回答

3. 调试流程区  
显示两种图：
- 静态 LangGraph 结构图
- 当前这次问诊真实执行过的节点流向图

同时还会列出本次执行的详细步骤，包括：

- 当前节点
- 节点做了什么
- 选中了哪条边
- 下一个节点是什么

## 项目整体架构

项目采用分层结构。

### 1. Web 层

目录：`src/medical_agent/web/`

职责：

- 提供 FastAPI 接口
- 提供 HTML 页面
- 把后端执行结果转换为前端可展示的数据

核心文件：

- `src/medical_agent/web/app.py`
- `src/medical_agent/web/index.html`

### 2. Graph 层

目录：`src/medical_agent/graph/`

职责：

- 定义 LangGraph 状态
- 注册节点
- 配置普通边和条件边
- 控制整个问诊流程如何流转

核心文件：

- `src/medical_agent/graph/builder.py`
- `src/medical_agent/graph/nodes.py`
- `src/medical_agent/graph/state.py`
- `src/medical_agent/graph/routing.py`

### 3. Service 层

目录：`src/medical_agent/services/`

职责：

- 封装 LLM 调用
- 封装联网搜索调用
- 让图节点不直接耦合底层 SDK

核心文件：

- `src/medical_agent/services/llm_service.py`
- `src/medical_agent/services/search_service.py`

### 4. 配置与模型层

目录：

- `src/medical_agent/config.py`
- `src/medical_agent/schemas.py`
- `src/medical_agent/prompts.py`

职责：

- 读取环境变量
- 统一请求/响应模型
- 统一管理系统提示词和节点提示词

## 核心代码是哪些

最核心的代码有四组：

1. 图构建  
`src/medical_agent/graph/builder.py`

2. 节点逻辑  
`src/medical_agent/graph/nodes.py`

3. Web API  
`src/medical_agent/web/app.py`

4. 前端调试可视化  
`src/medical_agent/web/index.html`

## 当前图的执行逻辑

主流程如下：

`understand -> search -> answer`

带条件分支：

- 如果信息不足：`understand -> clarify`
- 如果搜索结果不足：`search -> rewrite -> search`
- 如果搜索彻底失败：`search -> fallback`

## 注意事项

- 这是医疗信息辅助系统，不是确诊系统
- 遇到胸痛、呼吸困难、意识障碍、大出血等问题，系统应优先建议立即线下就医
- `.env` 中请保管好真实密钥，不要提交到公开仓库
