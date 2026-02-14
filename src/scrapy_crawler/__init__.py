"""
Scrapy 爬虫模块
使用 Scrapy 框架重构的爬虫实现
"""

from .manager import ScrapyFetchManager, ScrapyCrawlerRunner
from .items import ArticleItem, FetchResultItem
from .runner import load_site_configs

__all__ = [
    "ScrapyFetchManager",
    "ScrapyCrawlerRunner",
    "ArticleItem",
    "FetchResultItem",
    "load_site_configs",
]


