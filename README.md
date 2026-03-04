# HR 试用期专业指标润色（效果验证）

一个基于 **Streamlit + Excel + 大模型 API** 的验证工具：
- 从岗位画像 Excel 读取岗位上下文；
- 用户选择岗位并输入“专业指标简单描述”；
- 调用大模型输出更贴合岗位、专业且可落地的润色结果。

## 1. 准备

将 Excel 文件放在项目根目录（默认文件名）：

`岗位群画像列表_2026年02月06日18时32分.xlsx`

Excel 需要包含以下列名：
- 岗位群名称
- 职群
- 岗位群职级范围
- 岗位层级
- 关联岗位名称
- 关联岗位职类
- 定位
- 核心职责
- 关键业务活动
- 关键经验
- 关键能力
- 关键特质(可选)
- 基于业务特性/挑战。

## 2. 安装依赖

```bash
pip install -r requirements.txt
```

## 3. 运行

```bash
streamlit run app.py
```

## 4. 大模型配置

页面侧边栏支持配置：
- API Key（也支持环境变量 `LLM_API_KEY`）
- User Tag（默认：`人工智能部-HR项目`）
- 超时秒数（默认 90）
- 重试次数（默认 1）

调用接口固定为：
- URL: `https://llmops-new.haid.com.cn/v1/chat-messages`
- 请求头：
  - `Authorization: Bearer <api_key>`
  - `Content-Type: application/json`
- Body：
  - `inputs: {}`
  - `query: <prompt>`
  - `response_mode: blocking`
  - `conversation_id: <id>`
  - `user: <user_tag>`

## 5. 注意

当前为“效果验证阶段”，直接读取 Excel 作为 prompt 上下文来源。
