"""
Scrapy Item 定义
映射到现有的数据模型
"""

import scrapy
from scrapy.item import Field


class FetchResultItem(scrapy.Item):
    """
    抓取结果 Item
    对应原有的 FetchResult 模型
    """
    # 任务信息
    task_id = Field()
    url = Field()
    site_name = Field()
    site_config = Field()

    # 抓取状态
    status = Field()  # success, failed, skipped
    method = Field()  # scrapy, playwright
    page_type = Field()  # list, content

    # 内容
    html = Field()
    text = Field()

    # 解析结果
    title = Field()
    description = Field()
    parsed_data = Field()

    # 元信息
    status_code = Field()
    response_time_ms = Field()
    error_message = Field()
    fetched_at = Field()


class ArticleItem(scrapy.Item):
    """
    文章/项目 Item
    对应原有的 Article 模型
    """
    id = Field()
    source = Field()
    url = Field()

    # 基础信息
    title = Field()
    description = Field()

    # 列表页解析的额外字段
    language = Field()
    stars = Field()
    forks = Field()
    stars_today = Field()
    tags = Field()
    author = Field()

    # 详情页内容
    readme = Field()
    content = Field()
    markdown = Field()

    # AI 脱水结果 (由后续 pipeline 填充)
    summary = Field()
    core_value = Field()
    tech_stack = Field()
    recommendation = Field()
    score = Field()


class ListPageItem(scrapy.Item):
    """
    列表页解析结果
    包含多个子项目
    """
    site_name = Field()
    url = Field()
    title = Field()
    items = Field()  # List[ArticleItem]
    metadata = Field()

