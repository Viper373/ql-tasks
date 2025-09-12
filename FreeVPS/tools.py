# -*- coding:utf-8 -*-
# @Software       :PyCharm
# @Project        :AutoTasks
# @Path           :/FreeVPS
# @FileName       :tools.py
# @Time           :2025/9/10 20:18
# @Author         :Viper373
# @GitHub         :https://github.com/Viper373
# @Home           :https://viper3.top
# @Blog           :https://blog.viper3.top

from datetime import datetime, timedelta
import requests
from lxml import etree
from deep_translator import GoogleTranslator
from markdownify import markdownify as md
from bs4 import BeautifulSoup


def translate_text(text: str, origin_lang: str, target_lang: str) -> str:
    """
    使用 deep-translator 翻译文本，支持长文本分段翻译
    :param text: 待翻译文本
    :param origin_lang: 源语言
    :param target_lang: 目标语言
    :return: 翻译结果
    """
    if not text or not text.strip():
        return ""

    # 如果文本长度小于4000字符，直接翻译
    if len(text) <= 4000:
        try:
            translator = GoogleTranslator(source=origin_lang, target=target_lang)
            return translator.translate(text)
        except Exception as e:
            print(f"翻译失败: {e}")
            return text

    # 长文本分段翻译
    translator = GoogleTranslator(source=origin_lang, target=target_lang)
    translated_parts = []

    # 按段落分割文本
    paragraphs = text.split('\n\n')
    current_chunk = ""

    for paragraph in paragraphs:
        # 如果当前段落加上现有块超过4000字符，先翻译现有块
        if len(current_chunk + paragraph) > 4000 and current_chunk:
            try:
                result = translator.translate(current_chunk)
                translated_parts.append(result)
                current_chunk = paragraph
            except Exception as e:
                print(f"翻译块失败: {e}")
                translated_parts.append(current_chunk)
                current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph

    # 翻译最后一块
    if current_chunk:
        try:
            result = translator.translate(current_chunk)
            translated_parts.append(result)
        except Exception as e:
            print(f"翻译最后块失败: {e}")
            translated_parts.append(current_chunk)

    return "\n\n".join(translated_parts)


def html_to_md(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    seen_src = set()  # 用来记录已经处理过的图片 URL

    for img in soup.find_all("img"):
        src = img.get("src", "")
        # 替换 base64 占位图片
        if src.startswith("data:image"):
            new_src = img.get("data-lazy-src") or img.get("data-src")
            if new_src:
                img["src"] = new_src
            else:
                img.decompose()
                continue
        # 去掉重复图片
        src = img.get("src")
        if src in seen_src:
            img.decompose()  # 删除重复
        else:
            seen_src.add(src)

    clean_html = str(soup)
    return md(clean_html, heading_style="ATX")


def get_vps_article():
    """
    获取 VPS 文章内容，优先匹配两天前的文章
    :return: (title, content_md)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get("https://www.zrblog.net/", headers=headers, timeout=10)
    html = etree.HTML(response.text)
    articles = html.xpath("//article")

    today = datetime.today().date()

    def find_article_by_date(date_str: str):
        """根据日期字符串查找文章，返回 (标题, MD内容)"""
        for article in articles:
            pub_time = article.xpath(".//time/text()")
            if not pub_time:
                continue
            pub_time = pub_time[0].strip()
            if pub_time == date_str:
                link = article.xpath(".//h2/a/@href")
                link = link[0] if link else None
                if not link:
                    return f"找到文章但没有链接（日期：{pub_time}）", ""

                # 请求文章详情页
                detail_resp = requests.get(link, headers=headers, timeout=10)
                detail_html = etree.HTML(detail_resp.text)

                # 提取标题
                title = detail_html.xpath('//h1[@class="article-title"]/a/text()')
                title = title[0].strip() if title else "无标题"

                # 提取内容 HTML
                content_nodes = detail_html.xpath('//article[@class="article-content"]')
                if not content_nodes:
                    return title, "（未提取到正文内容）"

                content_html = etree.tostring(content_nodes[0], encoding="utf-8").decode("utf-8")

                # 转 Markdown
                content_md = html_to_md(content_html)

                return title, content_md
        return None

    # ① 先检查两天前的文章
    target_date = today - timedelta(days=2)
    target_str = target_date.strftime("%Y-%m-%d")
    result = find_article_by_date(target_str)
    if result:
        return result

    # ② 如果两天前没有，再从 3 天前往前推，跳过今天和昨天
    for days in range(3, 30):
        target_date = today - timedelta(days=days)
        target_str = target_date.strftime("%Y-%m-%d")
        result = find_article_by_date(target_str)
        if result:
            return result

    return "未找到文章", ""
