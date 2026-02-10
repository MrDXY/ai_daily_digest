"""
AI Provider - 提供 AI 基础能力

职责：
- 封装不同 AI provider 的调用接口
- 提供统一的 AI 调用方法
- 支持 Claude, OpenAI, Azure OpenAI, 自定义模型等多种后端
"""

import os
import logging
from typing import Optional, Any, Dict
from enum import Enum

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    """AI Provider 错误基类"""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.cause = cause


class RateLimitError(AIProviderError):
    """速率限制错误"""
    pass


class AIProvider(Enum):
    """AI Provider 类型"""
    CLAUDE = "claude"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    CUSTOM = "custom"


class AIProviderClient:
    """
    AI Provider 客户端

    提供统一的 AI 调用接口，支持多种后端
    使用异步客户端，支持重试和错误处理
    """

    def __init__(self, config: Any):
        """
        初始化 AI Provider

        Args:
            config: AppConfig 对象（包含 ai 属性）
        """
        self.config = config
        self.provider_name = config.ai.default_provider
        self.provider = AIProvider(self.provider_name)

        # 获取当前 provider 的配置
        self.provider_config = getattr(config.ai, self.provider_name)

        # 客户端延迟初始化
        self._client = None

        logger.info(f"Initialized AI provider: {self.provider_name}")

    def _resolve_env_var(self, value: str) -> str:
        """
        解析环境变量

        如果值以 ${VAR_NAME} 格式，则从环境变量读取
        """
        if value.startswith("${") and value.endswith("}"):
            var_name = value[2:-1]
            env_value = os.getenv(var_name)
            if not env_value:
                raise ValueError(
                    f"Environment variable {var_name} not set"
                )
            return env_value
        return value

    def _get_client(self):
        """获取或创建客户端（延迟初始化）"""
        if self._client is None:
            if self.provider == AIProvider.CLAUDE:
                self._client = self._create_claude_client()
            elif self.provider == AIProvider.OPENAI:
                self._client = self._create_openai_client()
            elif self.provider == AIProvider.AZURE_OPENAI:
                self._client = self._create_azure_openai_client()
            elif self.provider == AIProvider.CUSTOM:
                self._client = self._create_custom_client()
            else:
                raise ValueError(f"Unsupported AI provider: {self.provider_name}")
        return self._client

    def _create_claude_client(self):
        """创建 Claude 异步客户端"""
        try:
            from anthropic import AsyncAnthropic

            api_key = self._resolve_env_var(self.provider_config.api_key)
            return AsyncAnthropic(api_key=api_key)

        except ImportError:
            raise ImportError(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )

    def _create_openai_client(self):
        """创建 OpenAI 异步客户端"""
        try:
            from openai import AsyncOpenAI

            api_key = self._resolve_env_var(self.provider_config.api_key)
            return AsyncOpenAI(api_key=api_key)

        except ImportError:
            raise ImportError(
                "openai package not installed. "
                "Install with: pip install openai"
            )

    def _create_azure_openai_client(self):
        """创建 Azure OpenAI 异步客户端"""
        try:
            from openai import AsyncAzureOpenAI

            api_key = self._resolve_env_var(self.provider_config.api_key)
            api_base = self._resolve_env_var(self.provider_config.api_base)
            api_version = self._resolve_env_var(self.provider_config.api_version)

            return AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=api_base,
                api_version=api_version,
            )

        except ImportError:
            raise ImportError(
                "openai package not installed. "
                "Install with: pip install openai"
            )

    def _create_custom_client(self) -> httpx.AsyncClient:
        """创建自定义 OpenAI 兼容的 HTTP 客户端"""
        api_key = self._resolve_env_var(self.provider_config.api_key)
        api_base = self._resolve_env_var(self.provider_config.api_base)

        headers = {
            "Content-Type": "application/json",
        }

        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # 合并额外请求头
        extra_headers = getattr(self.provider_config, 'extra_headers', {})
        if extra_headers:
            headers.update(extra_headers)

        return httpx.AsyncClient(
            base_url=api_base,
            headers=headers,
            timeout=60.0,
        )

    async def generate_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        生成文本

        Args:
            prompt: 用户提示词
            system: 系统提示词（可选）
            max_tokens: 最大 token 数（可选）
            temperature: 温度参数（可选）

        Returns:
            生成的文本内容
        """
        # 使用默认值
        max_tokens = max_tokens or self.provider_config.max_tokens
        temperature = temperature or self.provider_config.temperature

        if self.provider == AIProvider.CLAUDE:
            return await self._generate_claude(prompt, system, max_tokens, temperature)
        elif self.provider == AIProvider.OPENAI:
            return await self._generate_openai(prompt, system, max_tokens, temperature)
        elif self.provider == AIProvider.AZURE_OPENAI:
            return await self._generate_azure_openai(prompt, system, max_tokens, temperature)
        elif self.provider == AIProvider.CUSTOM:
            return await self._generate_custom(prompt, system, max_tokens, temperature)
        else:
            raise ValueError(f"Unsupported provider: {self.provider_name}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def _generate_claude(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """使用 Claude 生成文本"""
        try:
            client = self._get_client()
            messages = [{"role": "user", "content": prompt}]

            response = await client.messages.create(
                model=self.provider_config.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "You are a helpful assistant.",
                messages=messages,
            )

            return response.content[0].text

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str and "limit" in error_str:
                raise RateLimitError(
                    f"Claude rate limit exceeded",
                    provider=self.provider_name,
                    model=self.provider_config.model,
                    cause=e,
                )
            raise AIProviderError(
                f"Claude API error: {e}",
                provider=self.provider_name,
                model=self.provider_config.model,
                cause=e,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def _generate_openai(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """使用 OpenAI 生成文本"""
        try:
            client = self._get_client()

            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = await client.chat.completions.create(
                model=self.provider_config.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
            )

            return response.choices[0].message.content

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str and "limit" in error_str:
                raise RateLimitError(
                    f"OpenAI rate limit exceeded",
                    provider=self.provider_name,
                    model=self.provider_config.model,
                    cause=e,
                )
            raise AIProviderError(
                f"OpenAI API error: {e}",
                provider=self.provider_name,
                model=self.provider_config.model,
                cause=e,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def _generate_azure_openai(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """使用 Azure OpenAI 生成文本"""
        try:
            client = self._get_client()

            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = await client.chat.completions.create(
                model=self.provider_config.deployment_name,  # Azure 使用 deployment name
                max_completion_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
            )

            return response.choices[0].message.content

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                raise RateLimitError(
                    f"Azure OpenAI rate limit exceeded",
                    provider=self.provider_name,
                    model=self.provider_config.deployment_name,
                    cause=e,
                )
            raise AIProviderError(
                f"Azure OpenAI API error: {e}",
                provider=self.provider_name,
                model=self.provider_config.deployment_name,
                cause=e,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def _generate_custom(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """使用自定义 OpenAI 兼容接口生成文本"""
        try:
            client = self._get_client()

            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.provider_config.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            response = await client.post(
                "/chat/completions",
                json=payload,
            )
            response.raise_for_status()

            data = response.json()
            return data["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError(
                    f"Custom model rate limit exceeded",
                    provider=self.provider_name,
                    model=self.provider_config.model,
                    cause=e,
                )
            raise AIProviderError(
                f"Custom model API error: {e}",
                provider=self.provider_name,
                model=self.provider_config.model,
                cause=e,
            )

        except Exception as e:
            raise AIProviderError(
                f"Custom model error: {e}",
                provider=self.provider_name,
                model=self.provider_config.model,
                cause=e,
            )

    async def generate_structured_output(
        self,
        prompt: str,
        system: Optional[str] = None,
        json_schema: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict:
        """
        生成结构化输出（JSON）

        Args:
            prompt: 用户提示词
            system: 系统提示词（可选）
            json_schema: JSON Schema（可选，用于约束输出格式）
            max_tokens: 最大 token 数（可选）
            temperature: 温度参数（可选）

        Returns:
            解析后的 JSON 对象
        """
        import json

        # 在 prompt 中添加 JSON 格式要求
        enhanced_prompt = f"{prompt}\n\n请以 JSON 格式返回结果。"

        if json_schema:
            enhanced_prompt += f"\n\nJSON Schema:\n```json\n{json.dumps(json_schema, indent=2)}\n```"

        # 生成文本
        response_text = await self.generate_text(
            enhanced_prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # 提取 JSON（处理可能包含 markdown 代码块的情况）
        json_text = response_text.strip()

        # 移除可能的 markdown 代码块标记
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        elif json_text.startswith("```"):
            json_text = json_text[3:]

        if json_text.endswith("```"):
            json_text = json_text[:-3]

        json_text = json_text.strip()

        # 解析 JSON
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text}")
            raise ValueError(f"Invalid JSON response from AI: {e}")

    async def close(self) -> None:
        """释放客户端资源"""
        if self._client is not None:
            if self.provider == AIProvider.CUSTOM:
                # httpx.AsyncClient 需要使用 aclose
                await self._client.aclose()
            else:
                # anthropic 和 openai 的异步客户端
                await self._client.close()
            self._client = None
            logger.debug(f"Closed AI provider client: {self.provider_name}")


def create_ai_provider(config: Any) -> AIProviderClient:
    """
    创建 AI Provider 实例（工厂函数）

    Args:
        config: 应用配置对象

    Returns:
        AIProviderClient 实例
    """
    return AIProviderClient(config)
