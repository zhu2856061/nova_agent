import base64
import os
from io import BytesIO


def get_img_base64(file_name: str) -> str:
    """
    get_img_base64 used in streamlit.
    absolute local path not working on windows.
    """
    image_path = os.path.join(os.path.dirname(__file__), "img", file_name)
    # 读取图片
    with open(image_path, "rb") as f:
        buffer = BytesIO(f.read())
        base_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{base_str}"
