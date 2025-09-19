# -*- coding: utf-8 -*-
# @Time   : 2025/09/19 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition

import hashlib
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

# 配置日志
logger = logging.getLogger(__name__)


class SogouCookieManager:
    """Cookie池管理类，负责Cookie的生成、验证和更新"""

    def __init__(self, cookie_expiry_hours: int = 24):
        self.cookie_pool = []  # 存储格式: (cookies_dict, create_time)
        self.expiry_hours = cookie_expiry_hours
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Edg/137.0.0.0",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.6723.71 Mobile Safari/537.36",
        ]

        # 初始化Cookie池
        self._init_cookie_pool(min_size=2)

    def _init_cookie_pool(self, min_size: int):
        """初始化Cookie池，确保有足够的有效Cookie"""
        logger.info(f"初始化Cookie池，目标数量: {min_size}")
        while len(self.cookie_pool) < min_size:
            self._add_new_cookie()
            time.sleep(random.uniform(2, 4))  # 避免集中创建

    def _generate_base_cookies(self) -> dict:
        """生成基础Cookie信息"""
        timestamp = int(time.time() * 1000)
        suid = hashlib.md5(str(timestamp).encode()).hexdigest().upper()

        return {
            "ABTEST": f"7|{timestamp}|v1",
            "SUID": suid,
            "IPLOC": f"CN{random.randint(1100, 6500)}",  # 模拟不同地区
            "SUV": f"{random.randint(10000000, 99999999)}{timestamp}",
            "SNUID": hashlib.md5(str(random.random()).encode()).hexdigest().upper(),
        }

    def _add_new_cookie(self) -> bool:
        """创建并验证新Cookie，成功则加入池"""
        try:
            session = requests.Session()
            headers = self._get_random_headers()

            # 访问主页获取完整Cookie
            session.get(
                "https://weixin.sogou.com/",
                headers=headers,
                timeout=10,
                allow_redirects=True,
            )

            # 验证Cookie有效性
            test_url = "https://weixin.sogou.com/weixin?type=2&query=科技"
            response = session.get(test_url, headers=headers, timeout=10)

            if "antispider" not in response.text and response.status_code == 200:
                # 转换为Cookie字典
                cookie_dict = {cookie.name: cookie.value for cookie in session.cookies}
                self.cookie_pool.append((cookie_dict, datetime.now()))
                logger.info(f"新Cookie添加成功，当前池大小: {len(self.cookie_pool)}")
                return True
            else:
                logger.warning("新Cookie验证失败")
                return False

        except Exception as e:
            logger.error(f"创建Cookie失败: {str(e)}")
            return False

    def _get_random_headers(self) -> dict:
        """获取随机请求头"""
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": random.choice(self.user_agents),
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        }

    def get_valid_cookie(self) -> Optional[dict]:
        """获取一个有效的Cookie，移除过期的"""
        # 清理过期Cookie
        now = datetime.now()
        self.cookie_pool = [
            (cookie, create_time)
            for cookie, create_time in self.cookie_pool
            if now - create_time < timedelta(hours=self.expiry_hours)
        ]

        # 如果Cookie不足，补充新的
        if len(self.cookie_pool) < 2:
            logger.info("Cookie池数量不足，补充新Cookie")
            self._add_new_cookie()

        return random.choice(self.cookie_pool)[0] if self.cookie_pool else None


class SogouUrlFetcher:
    """搜狗微信链接解析器"""

    def __init__(self):
        self.cookie_manager = SogouCookieManager()
        self.request_interval = (2, 5)  # 请求间隔范围(秒)
        self.last_request_time = 0
        self.max_retries = 3

    def _wait_for_rate_limit(self):
        """控制请求频率，避免过快"""
        elapsed = time.time() - self.last_request_time
        required_wait = random.uniform(*self.request_interval) - elapsed

        if required_wait > 0:
            time.sleep(required_wait)
        self.last_request_time = time.time()

    def get_real_url(self, sogou_url: str) -> str:
        """获取真实微信文章链接"""
        if not sogou_url:
            return ""

        for retry in range(self.max_retries):
            try:
                self._wait_for_rate_limit()

                # 获取随机Cookie和 headers
                cookie_dict = self.cookie_manager.get_valid_cookie()
                if not cookie_dict:
                    logger.error("没有可用的Cookie")
                    time.sleep(5)
                    continue

                headers = self.cookie_manager._get_random_headers()
                headers["Cookie"] = "; ".join(
                    [f"{k}={v}" for k, v in cookie_dict.items()]
                )

                # 发送请求
                session = requests.Session()
                response = session.get(
                    sogou_url, headers=headers, timeout=15, allow_redirects=True
                )

                # 检查是否触发反爬
                if "antispider" in response.text or "验证码" in response.text:
                    logger.warning(f"第{retry + 1}次尝试触发反爬，更换Cookie")
                    # 移除当前可能已被标记的Cookie
                    if cookie_dict in [c for c, _ in self.cookie_manager.cookie_pool]:
                        self.cookie_manager.cookie_pool = [
                            (c, t)
                            for c, t in self.cookie_manager.cookie_pool
                            if c != cookie_dict
                        ]
                    time.sleep(random.uniform(5, 8))
                    continue

                # 检查是否直接跳转
                if "mp.weixin.qq.com" in response.url:
                    return response.url

                # 解析页面中的链接
                script_content = response.text
                url_parts = []
                start_index = 0

                while True:
                    part_start = script_content.find("url += '", start_index)
                    if part_start == -1:
                        break
                    part_end = script_content.find("'", part_start + len("url += '"))
                    if part_end == -1:
                        break
                    url_parts.append(
                        script_content[part_start + len("url += '") : part_end]
                    )
                    start_index = part_end + 1

                full_url = "".join(url_parts).replace("@", "")
                if full_url:
                    # 补全URL格式
                    if full_url.startswith("//"):
                        return f"https:{full_url}"
                    elif not full_url.startswith("http"):
                        return f"https://{full_url}"
                    return full_url

            except Exception as e:
                logger.error(f"第{retry + 1}次尝试失败: {str(e)}")
                time.sleep(random.uniform(3, 6))

        logger.error(f"多次尝试后仍无法获取链接: {sogou_url}")
        return ""
