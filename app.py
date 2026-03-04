import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

EXCEL_DEFAULT = "岗位群画像列表_2026年02月06日18时32分.xlsx"
DEFAULT_LLM_URL = "https://llmops-new.haid.com.cn/v1/chat-messages"
REQUIRED_COLUMNS = [
    "岗位群名称",
    "职群",
    "岗位群职级范围",
    "岗位层级",
    "关联岗位名称",
    "关联岗位职类",
    "定位",
    "核心职责",
    "关键业务活动",
    "关键经验",
    "关键能力",
    "关键特质(可选)",
    "基于业务特性/挑战。",
]


@dataclass
class LLMConfig:
    url: str = DEFAULT_LLM_URL
    api_key: str = ""
    user_tag: str = "人工智能部-HR项目"
    timeout_sec: int = 90
    max_retries: int = 1


class LLMClient:
    """封装内部大模型调用：POST /v1/chat-messages"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._session = requests.Session()

    def polish(self, prompt: str, conversation_id: Optional[str] = None) -> Tuple[str, str]:
        if not self.config.api_key:
            raise ValueError("未检测到 API Key，请先在页面中输入，或设置环境变量 LLM_API_KEY。")

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": {},
            "query": prompt,
            "response_mode": "blocking",
            "conversation_id": conversation_id or "",
            "user": self.config.user_tag,
        }

        last_error = ""
        for attempt in range(int(self.config.max_retries) + 1):
            start = time.monotonic()
            try:
                resp = self._session.post(
                    self.config.url,
                    headers=headers,
                    json=payload,
                    timeout=int(self.config.timeout_sec),
                )
                latency_ms = int((time.monotonic() - start) * 1000)

                if resp.status_code != 200:
                    last_error = (
                        f"http_status={resp.status_code}, latency_ms={latency_ms}, "
                        f"url={self.config.url}, resp={self._safe_text(resp)}"
                    )
                    continue

                try:
                    data = resp.json()
                except Exception as e:
                    raise RuntimeError(
                        f"响应解析失败: json parse fail: {e}; url={self.config.url}; "
                        f"latency_ms={latency_ms}; resp={self._safe_text(resp)}"
                    )

                answer = (data.get("answer") or "").strip()
                if not answer:
                    answer = self._extract_answer(data).strip()

                if not answer:
                    raise RuntimeError(
                        f"响应为空: url={self.config.url}; latency_ms={latency_ms}; raw={str(data)[:500]}"
                    )

                next_conversation_id = data.get("conversation_id", conversation_id or "")
                return answer, next_conversation_id
            except requests.RequestException as e:
                latency_ms = int((time.monotonic() - start) * 1000)
                last_error = (
                    f"request_exception={type(e).__name__}: {e}; "
                    f"url={self.config.url}; latency_ms={latency_ms}"
                )

        raise RuntimeError(f"调用大模型失败: {last_error or 'unknown error'}")

    @staticmethod
    def _safe_text(resp: requests.Response, limit: int = 500) -> str:
        return (resp.text or "").strip().replace("\n", " ")[:limit]

    @staticmethod
    def _extract_answer(data: Dict[str, Any]) -> str:
        if "answer" in data and isinstance(data["answer"], str):
            return data["answer"]
        if "data" in data and isinstance(data["data"], dict):
            inner = data["data"]
            if "answer" in inner and isinstance(inner["answer"], str):
                return inner["answer"]
        if "output" in data and isinstance(data["output"], str):
            return data["output"]
        return ""


@st.cache_data(show_spinner=False)
def load_excel(file_path: str) -> pd.DataFrame:
    df = pd.read_excel(file_path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Excel 缺少必要列: {missing}")
    df = df[REQUIRED_COLUMNS].copy()
    df["关联岗位名称"] = df["关联岗位名称"].astype(str).str.strip()
    return df


def build_prompt(row: pd.Series, user_input: str) -> str:
    return f"""你是资深HR专家与业务管理教练，擅长将试用期专业指标润色为“更贴合岗位、更专业、更可落地”的表述。

请结合以下岗位画像信息，对“用户输入的专业指标描述”进行润色。

【岗位画像信息】
- 岗位群名称：{row['岗位群名称']}
- 职群：{row['职群']}
- 岗位群职级范围：{row['岗位群职级范围']}
- 岗位层级：{row['岗位层级']}
- 关联岗位名称：{row['关联岗位名称']}
- 关联岗位职类：{row['关联岗位职类']}
- 定位：{row['定位']}
- 核心职责：{row['核心职责']}
- 关键业务活动：{row['关键业务活动']}
- 关键经验：{row['关键经验']}
- 关键能力：{row['关键能力']}
- 关键特质(可选)：{row['关键特质(可选)']}
- 基于业务特性/挑战：{row['基于业务特性/挑战。']}

【用户输入的专业指标描述】
{user_input}

请按以下要求输出：
1) 输出“润色后描述”（1段，简洁专业，突出岗位贴合度与可执行性）。
2) 输出“落地建议”（3条以内，动作化、可衡量，便于试用期跟踪）。
3) 不要编造与岗位无关内容，不要空泛套话。
"""


def main() -> None:
    st.set_page_config(page_title="HR试用期专业指标润色验证", layout="wide")
    st.title("HR试用期专业指标润色（效果验证版）")
    st.caption("通过 Excel 岗位画像 + 用户输入描述，调用大模型生成岗位贴合的润色结果。")

    with st.sidebar:
        st.subheader("配置")
        excel_path = st.text_input("Excel 文件路径", value=EXCEL_DEFAULT)
        llm_url = st.text_input("LLM URL", value=os.getenv("LLM_URL", DEFAULT_LLM_URL))
        api_key = st.text_input(
            "API Key",
            value=os.getenv("LLM_API_KEY", ""),
            type="password",
            help="优先读取这里填写的值，未填写时可使用环境变量 LLM_API_KEY。",
        )
        user_tag = st.text_input("User Tag", value=os.getenv("LLM_USER_TAG", "人工智能部-HR项目"))
        timeout_sec = st.number_input("超时时间（秒）", min_value=5, max_value=300, value=90)
        max_retries = st.number_input("重试次数", min_value=0, max_value=5, value=1)

    if "conversation_id" not in st.session_state:
        st.session_state["conversation_id"] = str(uuid.uuid4())

    if not os.path.exists(excel_path):
        st.warning(f"未找到 Excel 文件：{excel_path}。请将文件放到项目目录或填写正确路径。")
        st.stop()

    try:
        df = load_excel(excel_path)
    except Exception as e:
        st.error(f"读取 Excel 失败：{e}")
        st.stop()

    posts = sorted([p for p in df["关联岗位名称"].dropna().unique().tolist() if str(p).strip()])
    if not posts:
        st.error("Excel 中未发现可用的‘关联岗位名称’。")
        st.stop()

    selected_post = st.selectbox("请选择岗位名称（关联岗位名称）", posts)
    selected_row = df[df["关联岗位名称"] == selected_post].iloc[0]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 岗位背景信息")
        st.json(
            {
                "岗位群名称": selected_row["岗位群名称"],
                "职群": selected_row["职群"],
                "岗位群职级范围": selected_row["岗位群职级范围"],
                "岗位层级": selected_row["岗位层级"],
                "定位": selected_row["定位"],
                "核心职责": selected_row["核心职责"],
                "关键业务活动": selected_row["关键业务活动"],
            }
        )

    with c2:
        st.markdown("### 输入专业指标描述")
        user_input = st.text_area(
            "请填写专业指标的简单描述",
            placeholder="例如：负责搭建招聘数据看板，提升岗位到面效率，并优化试用期人才评估机制。",
            height=220,
        )

        if st.button("生成润色结果", type="primary"):
            if not user_input.strip():
                st.warning("请先输入专业指标描述。")
            else:
                prompt = build_prompt(selected_row, user_input.strip())
                client = LLMClient(
                    LLMConfig(
                        url=llm_url,
                        api_key=api_key,
                        user_tag=user_tag,
                        timeout_sec=int(timeout_sec),
                        max_retries=int(max_retries),
                    )
                )
                with st.spinner("大模型生成中..."):
                    try:
                        answer, conv_id = client.polish(
                            prompt=prompt,
                            conversation_id=st.session_state["conversation_id"],
                        )
                        st.session_state["conversation_id"] = conv_id
                        st.success("已生成润色结果")
                        st.markdown("### 润色输出")
                        st.write(answer)
                        st.download_button(
                            "下载本次结果(txt)",
                            data=answer.encode("utf-8"),
                            file_name=f"{selected_post}_润色结果.txt",
                            mime="text/plain",
                        )
                    except Exception as e:
                        st.error(f"生成失败：{e}")
                        st.info("请确认 URL 必须是可直接 POST 的完整地址（例如 .../v1/chat-messages）。")


if __name__ == "__main__":
    main()
