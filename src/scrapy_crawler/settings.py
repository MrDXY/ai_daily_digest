# Scrapy settings for ai_daily_digest project

BOT_NAME = "ai_daily_digest"

SPIDER_MODULES = ["src.scrapy_crawler.spiders"]
NEWSPIDER_MODULE = "src.scrapy_crawler.spiders"

# Crawl responsibly by identifying yourself
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests
CONCURRENT_REQUESTS = 5

# Configure a delay for requests for the same website
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True

# Disable cookies (enabled by default)
COOKIES_ENABLED = True

# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
    "src.scrapy_crawler.middlewares.RandomUserAgentMiddleware": 400,
    "src.scrapy_crawler.middlewares.StealthMiddleware": 450,
    "src.scrapy_crawler.middlewares.RetryWithDelayMiddleware": 500,
}

# Configure item pipelines
ITEM_PIPELINES = {
    "src.scrapy_crawler.pipelines.ContentCleanerPipeline": 100,
    "src.scrapy_crawler.pipelines.ContentExtractorPipeline": 200,
    "src.scrapy_crawler.pipelines.ResultCollectorPipeline": 900,
}

# Enable and configure the AutoThrottle extension
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 3.0
AUTOTHROTTLE_DEBUG = False

# Configure download timeout
DOWNLOAD_TIMEOUT = 30

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 520, 521, 522, 523, 524, 408, 429]

# HTTP cache (disabled by default, enable for development)
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 86400
HTTPCACHE_DIR = "output/cache/httpcache"

# Set settings whose default value is deprecated
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

# Custom settings
CUSTOM_SETTINGS = {
    "request_delay_range": (0.5, 2.0),
    "max_details_per_site": 30,
}

