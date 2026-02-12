"""
数据模型定义
使用 Pydantic v2 进行数据验证和序列化
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class FetchMethod(str, Enum):
    """抓取方式"""
    LIGHT = "light"      # curl_cffi
    HEAVY = "heavy"      # Playwright
    CRAWL4AI = "crawl4ai"  # Crawl4AI
    UNKNOWN = "unknown"


class FetchPageType(str, Enum):
    """页面类型"""
    LIST = "list"          # 目录/列表页
    CONTENT = "content"    # 内容页
    UNKNOWN = "unknown"


class FetchStatus(str, Enum):
    """抓取状态"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class FetchTask(BaseModel):
    """抓取任务"""

    id: str = Field(..., description="任务唯一标识")
    url: str = Field(..., description="目标 URL")
    site_name: str = Field(..., description="站点名称")
    site_config: dict[str, Any] = Field(default_factory=dict, description="站点配置")
    priority: int = Field(default=0, description="优先级，数字越大优先级越高")
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class FetchResult(BaseModel):
    """抓取结果"""

    task_id: str = Field(..., description="关联的任务 ID")
    url: str = Field(..., description="实际抓取的 URL")
    status: FetchStatus = Field(default=FetchStatus.PENDING)
    method: FetchMethod = Field(default=FetchMethod.UNKNOWN)
    page_type: FetchPageType = Field(default=FetchPageType.UNKNOWN)

    # 内容
    html: Optional[str] = Field(default=None, description="原始 HTML")
    text: Optional[str] = Field(default=None, description="提取的纯文本")

    # 解析后的结构化数据
    title: Optional[str] = None
    description: Optional[str] = None
    parsed_data: dict[str, Any] = Field(default_factory=dict)

    # 元信息
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True


class Article(BaseModel):
    """文章/项目实体 - 经过 AI 脱水后的结构"""

    id: str = Field(..., description="唯一标识")
    source: str = Field(..., description="来源站点")
    url: str = Field(..., description="原始链接")

    # 基础信息
    title: str = Field(..., description="标题")
    description: Optional[str] = Field(default=None, description="原始描述")

    # AI 脱水结果
    summary: str = Field(..., description="AI 生成的摘要")
    core_value: str = Field(..., description="核心价值")
    tech_stack: list[str] = Field(default_factory=list, description="技术栈")
    recommendation: str = Field(..., description="推荐理由")
    score: float = Field(..., ge=0, le=100, description="评分 (0-100)")

    # 额外信息
    language: Optional[str] = None
    stars: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None

    @property
    def is_high_quality(self) -> bool:
        """是否为高质量项目 (评分 >= 80)"""
        return self.score >= 80.0

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        stars_display = f"⭐ {self.stars}" if self.stars else ""
        tech_display = ", ".join(self.tech_stack) if self.tech_stack else "N/A"

        return f"""### [{self.title}]({self.url}) {stars_display}

    **评分**: {'⭐' * int(self.score // 10)} ({self.score}/100)

**核心价值**: {self.core_value}

**技术栈**: {tech_display}

**摘要**: {self.summary}

**推荐理由**: {self.recommendation}

---
"""


class DigestReport(BaseModel):
    """日报报告"""

    date: str = Field(..., description="报告日期")
    total_fetched: int = Field(default=0, description="总抓取数")
    total_processed: int = Field(default=0, description="总处理数")
    high_quality_count: int = Field(default=0, description="高质量项目数")

    articles: list[Article] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    # 统计信息
    sources: dict[str, int] = Field(default_factory=dict, description="各来源文章数")
    avg_score: float = Field(default=0.0, description="平均评分")

    # 元信息
    generated_at: datetime = Field(default_factory=datetime.now)
    processing_time_seconds: float = Field(default=0.0)
    score_threshold: float = Field(default=80.0, description="高质量评分阈值")

    def get_high_quality_articles(self) -> list[Article]:
        """获取高质量文章列表"""
        return [a for a in self.articles if a.score >= self.score_threshold]

    def calculate_stats(self) -> None:
        """计算统计信息"""
        self.total_processed = len(self.articles)
        self.high_quality_count = len(self.get_high_quality_articles())

        if self.articles:
            self.avg_score = sum(a.score for a in self.articles) / len(self.articles)

            # 按来源统计
            self.sources = {}
            for article in self.articles:
                self.sources[article.source] = self.sources.get(article.source, 0) + 1
