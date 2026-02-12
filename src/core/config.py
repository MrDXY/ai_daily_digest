"""
配置加载器
支持环境变量替换和多层配置合并
"""

import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from .exceptions import ConfigException


class CacheConfig(BaseModel):
    """缓存配置"""
    enabled: bool = True
    cache_dir: str = "./output/cache"
    keep_days: int = 7


class CrawlerConfig(BaseModel):
    """爬虫配置"""
    concurrency: int = 5
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 2
    fetcher: str = "auto"
    list_depth: int = 1
    cache: CacheConfig = Field(default_factory=CacheConfig)
    user_agents: list[str] = Field(default_factory=list)
    playwright: dict[str, Any] = Field(default_factory=dict)
    crawl4ai: dict[str, Any] = Field(default_factory=dict)


class ClaudeConfig(BaseModel):
    """Claude 配置"""
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 2048
    temperature: float = 0.3


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI 配置"""
    api_key: str = ""
    api_base: str = ""
    api_version: str = "2024-02-15-preview"
    deployment_name: str = ""
    max_tokens: int = 2048
    temperature: float = 0.3


class OpenAIConfig(BaseModel):
    """OpenAI 配置"""
    api_key: str = ""
    model: str = "gpt-4o"
    max_tokens: int = 2048
    temperature: float = 0.3


class CustomModelConfig(BaseModel):
    """自定义模型配置"""
    api_key: str = ""
    api_base: str = ""
    model: str = ""
    max_tokens: int = 2048
    temperature: float = 0.3
    extra_headers: dict[str, str] = Field(default_factory=dict)


class AIConfig(BaseModel):
    """AI 配置"""
    default_provider: str = "azure_openai"
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    azure_openai: AzureOpenAIConfig = Field(default_factory=AzureOpenAIConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    custom: CustomModelConfig = Field(default_factory=CustomModelConfig)


class DigestConfig(BaseModel):
    """脱水配置"""
    score_threshold: int = 80
    batch_size: int = 10
    max_summary_length: int = 500


class OutputConfig(BaseModel):
    """输出配置"""
    report_filename: str = "daily_report_{date}.md"
    generate_json: bool = True
    terminal: dict[str, Any] = Field(default_factory=dict)


class SiteReference(BaseModel):
    """站点引用"""
    name: str
    enabled: bool = True
    config_file: str


class AppConfig(BaseModel):
    """应用主配置"""
    app: dict[str, Any] = Field(default_factory=dict)
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    digest: DigestConfig = Field(default_factory=DigestConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    sites: list[SiteReference] = Field(default_factory=list)

    # 加载后的站点配置
    site_configs: dict[str, dict[str, Any]] = Field(default_factory=dict)


def expand_env_vars(value: Any) -> Any:
    """
    递归展开环境变量
    支持 ${VAR_NAME} 和 $VAR_NAME 格式
    """
    if isinstance(value, str):
        # 匹配 ${VAR_NAME} 或 $VAR_NAME
        pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'

        def replacer(match):
            var_name = match.group(1) or match.group(2)
            return os.environ.get(var_name, "")

        return re.sub(pattern, replacer, value)

    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]

    return value


def load_yaml(file_path: Path) -> dict[str, Any]:
    """加载 YAML 文件"""
    if not file_path.exists():
        raise ConfigException(f"Config file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f)

    return expand_env_vars(content) if content else {}


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    加载应用配置

    Args:
        config_path: 配置文件路径，默认为 config/config.yaml

    Returns:
        AppConfig: 应用配置对象
    """
    # 确定配置目录
    if config_path:
        config_file = Path(config_path)
    else:
        # 从项目根目录查找
        config_file = Path(__file__).parent.parent.parent / "config" / "config.yaml"

    config_dir = config_file.parent

    # 加载主配置
    main_config = load_yaml(config_file)

    # 创建配置对象
    app_config = AppConfig(**main_config)

    # 加载各站点配置
    for site in app_config.sites:
        if site.enabled:
            site_config_path = config_dir / site.config_file
            if site_config_path.exists():
                app_config.site_configs[site.name] = load_yaml(site_config_path)

    return app_config


def get_config_dir() -> Path:
    """获取配置目录路径"""
    return Path(__file__).parent.parent.parent / "config"


def get_output_dir(app_config: AppConfig) -> Path:
    """获取输出目录路径"""
    output_dir = app_config.app.get("output_dir", "./output")
    path = Path(output_dir)

    # 如果是相对路径，相对于项目根目录
    if not path.is_absolute():
        path = Path(__file__).parent.parent.parent / output_dir

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_report_dir(app_config: AppConfig) -> Path:
    """获取报告目录路径"""
    output_dir = get_output_dir(app_config)
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def get_report_date_dir(app_config: AppConfig, date_str: str) -> Path:
    """获取指定日期报告目录路径（YYYY/MM/DD）"""
    report_dir = get_report_dir(app_config)
    parts = (date_str or "").split("-")
    if len(parts) != 3:
        return report_dir
    year, month, day = parts
    date_dir = report_dir / year / month / day
    date_dir.mkdir(parents=True, exist_ok=True)
    return date_dir


def get_cache_dir(app_config: AppConfig) -> Path:
    """获取缓存目录路径"""
    cache_dir = app_config.crawler.cache.cache_dir
    path = Path(cache_dir)

    # 如果是相对路径，相对于项目根目录
    if not path.is_absolute():
        path = Path(__file__).parent.parent.parent / cache_dir

    path.mkdir(parents=True, exist_ok=True)
    return path

