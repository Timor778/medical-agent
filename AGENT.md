# 医疗问诊 Agent 规范

用途：系统环境、命名规范、编码风格。

## 1. 系统环境

Windows 11 环境，命令请使用 PowerShell 风格，不使用 Mac/Linux 专用命令。
Get-Content -Raw -Encoding utf8 使用utf8编码查看文件，否则会出现乱码
## 2. 命名规范

- 类：大驼峰，例如 `MedicalSearchService`
- 方法：小驼峰或蛇形均可，但同模块内保持一致
- Graph 节点：语义明确的蛇形命名，例如 `understand_node`
- 接口模型：明确区分 `Request` 和 `Response`
- 常量：全大写加下划线

## 3. 编码风格

- 注释尽量少，但关键业务规则和复杂逻辑必须写明
- 不写重复代码含义的废话注释
- 注释重点写为什么这么做、业务约束和边界处理
