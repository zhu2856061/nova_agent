import streamlit as st
from component import llm_agent_page, llm_chat_page, llm_task_page
from utils import get_img_base64

if __name__ == "__main__":
    st.set_page_config(
        page_title="Nova 智能助手",
        page_icon=get_img_base64("nova_chat.png"),
        layout="wide",
    )
    with st.sidebar:
        st.logo(get_img_base64("title.png"), size="large")

    pg = st.navigation(
        {
            "📶Chat": [
                st.Page(
                    llm_chat_page,
                    title="Nova Chat",
                    icon=":material/chat_add_on:",
                ),
            ],
            "📶Agent": [
                st.Page(
                    llm_agent_page,
                    title="researcher",
                    icon=":material/chat_add_on:",
                ),
            ],
            "📶Team": [
                st.Page(
                    llm_task_page,
                    title="deepresearcher",
                    icon=":material/chat_add_on:",
                ),
            ],
        }
    )
    pg.run()
