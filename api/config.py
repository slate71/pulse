"""
Configuration management using Pydantic Settings.

Provides structured, validated configuration for all environments.
"""

import os
import logging
from enum import Enum
from functools import lru_cache
from typing import List, Optional, Set
try:
    from pydantic import BaseSettings, Field, validator
except ImportError:
    from pydantic_settings import BaseSettings
    from pydantic import Field, validator


class Environment(str, Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging" 
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    url: str = Field(..., env="DATABASE_URL", description="Database connection URL")
    min_connections: int = Field(1, env="DB_MIN_CONNECTIONS", description="Minimum pool connections")
    max_connections: int = Field(20, env="DB_MAX_CONNECTIONS", description="Maximum pool connections")
    command_timeout: int = Field(60, env="DB_COMMAND_TIMEOUT", description="Command timeout in seconds")
    query_timeout: int = Field(30, env="DB_QUERY_TIMEOUT", description="Query timeout in seconds")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_ignore_empty = True
    
    @validator("min_connections")
    def validate_min_connections(cls, v):
        if v < 1:
            raise ValueError("min_connections must be at least 1")
        return v
    
    @validator("max_connections")
    def validate_max_connections(cls, v, values):
        if v < values.get("min_connections", 1):
            raise ValueError("max_connections must be >= min_connections")
        return v


class SecuritySettings(BaseSettings):
    """Security configuration settings."""
    
    # CORS settings
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"],
        env="CORS_ORIGINS",
        description="Allowed CORS origins"
    )
    cors_credentials: bool = Field(True, env="CORS_CREDENTIALS")
    cors_methods: List[str] = Field(["GET", "POST", "PUT", "DELETE"], env="CORS_METHODS") 
    cors_headers: List[str] = Field(["*"], env="CORS_HEADERS")
    
    # Security headers
    hsts_max_age: int = Field(31536000, env="HSTS_MAX_AGE", description="HSTS max age in seconds")
    csp_policy: str = Field(
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        env="CSP_POLICY",
        description="Content Security Policy"
    )
    
    # Rate limiting
    rate_limit_requests: int = Field(100, env="RATE_LIMIT_REQUESTS", description="Requests per time window")
    rate_limit_window: int = Field(60, env="RATE_LIMIT_WINDOW", description="Rate limit window in seconds")
    
    # API Keys for external services
    api_key_header: str = Field("X-API-Key", env="API_KEY_HEADER")
    valid_api_keys: Set[str] = Field(default_factory=set, env="VALID_API_KEYS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_ignore_empty = True
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    @validator("cors_methods", pre=True)
    def parse_cors_methods(cls, v):
        if isinstance(v, str):
            return [method.strip().upper() for method in v.split(",") if method.strip()]
        return v
    
    @validator("cors_headers", pre=True)
    def parse_cors_headers(cls, v):
        if isinstance(v, str):
            return [header.strip() for header in v.split(",") if header.strip()]
        return v
    
    @validator("valid_api_keys", pre=True)
    def parse_api_keys(cls, v):
        if isinstance(v, str):
            keys = {key.strip() for key in v.split(",") if key.strip()}
            return keys
        return v or set()


class ExternalAPISettings(BaseSettings):
    """External API configuration."""
    
    # GitHub API
    github_token: Optional[str] = Field(None, env="GITHUB_TOKEN", description="GitHub API token")
    github_timeout: int = Field(30, env="GITHUB_TIMEOUT", description="GitHub API timeout in seconds")
    
    # Linear API  
    linear_api_key: Optional[str] = Field(None, env="LINEAR_API_KEY", description="Linear API key")
    linear_team_id: Optional[str] = Field(None, env="LINEAR_TEAM_ID", description="Linear team ID")
    linear_timeout: int = Field(30, env="LINEAR_TIMEOUT", description="Linear API timeout in seconds")
    
    # OpenAI API
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY", description="OpenAI API key")
    openai_timeout: int = Field(60, env="OPENAI_TIMEOUT", description="OpenAI API timeout in seconds")
    openai_model: str = Field("gpt-4", env="OPENAI_MODEL", description="OpenAI model to use")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_ignore_empty = True
    
    @property
    def github_enabled(self) -> bool:
        """Check if GitHub integration is enabled."""
        return bool(self.github_token)
    
    @property
    def linear_enabled(self) -> bool:
        """Check if Linear integration is enabled."""
        return bool(self.linear_api_key and self.linear_team_id)
    
    @property
    def openai_enabled(self) -> bool:
        """Check if OpenAI integration is enabled."""
        return bool(self.openai_api_key)


class ApplicationSettings(BaseSettings):
    """Application-level configuration."""
    
    # Basic app info
    title: str = Field("Pulse API", env="APP_TITLE", description="Application title")
    description: str = Field(
        "AI-powered engineering radar API", 
        env="APP_DESCRIPTION", 
        description="Application description"
    )
    version: str = Field("1.0.0", env="APP_VERSION", description="Application version")
    
    # Environment and deployment
    environment: Environment = Field(Environment.DEVELOPMENT, env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG", description="Enable debug mode")
    
    # Server settings
    host: str = Field("0.0.0.0", env="API_HOST", description="API server host")
    port: int = Field(8000, env="API_PORT", description="API server port")
    
    # Logging
    log_level: LogLevel = Field(LogLevel.INFO, env="LOG_LEVEL")
    log_format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    structured_logging: bool = Field(False, env="STRUCTURED_LOGGING")
    
    # Request handling
    request_timeout: int = Field(300, env="REQUEST_TIMEOUT", description="Request timeout in seconds") 
    max_request_size: int = Field(16 * 1024 * 1024, env="MAX_REQUEST_SIZE", description="Max request size in bytes")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_ignore_empty = True
    
    @validator("port")
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError("port must be between 1 and 65535")
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION


class Settings(BaseSettings):
    """Complete application settings."""
    
    # Sub-configurations
    app: ApplicationSettings = Field(default_factory=ApplicationSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    external_apis: ExternalAPISettings = Field(default_factory=ExternalAPISettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_ignore_empty = True
        
    def configure_logging(self):
        """Configure application logging based on settings."""
        logging.basicConfig(
            level=getattr(logging, self.app.log_level.value),
            format=self.app.log_format,
            force=True
        )
        
        # Set specific logger levels for noisy libraries
        if not self.app.debug:
            logging.getLogger("asyncio").setLevel(logging.WARNING)
            logging.getLogger("asyncpg").setLevel(logging.WARNING)
            
        logger = logging.getLogger(__name__)
        logger.info(f"Logging configured for {self.app.environment.value} environment")
    
    def validate_configuration(self):
        """Validate the complete configuration and log status."""
        logger = logging.getLogger(__name__)
        
        # Log environment and key settings
        logger.info(f"Environment: {self.app.environment.value}")
        logger.info(f"Debug mode: {self.app.debug}")
        logger.info(f"Database connections: {self.database.min_connections}-{self.database.max_connections}")
        
        # Log external API status
        if self.external_apis.github_enabled:
            logger.info("GitHub API integration: enabled")
        else:
            logger.info("GitHub API integration: disabled")
            
        if self.external_apis.linear_enabled:
            logger.info("Linear API integration: enabled")
        else:
            logger.info("Linear API integration: disabled")
            
        if self.external_apis.openai_enabled:
            logger.info(f"OpenAI API integration: enabled (model: {self.external_apis.openai_model})")
        else:
            logger.info("OpenAI API integration: disabled - using fallback reasoning")
        
        # Validate production-specific settings
        if self.app.is_production:
            if self.app.debug:
                logger.warning("Debug mode is enabled in production - consider disabling")
            
            if "localhost" in str(self.security.cors_origins):
                logger.warning("Localhost origins allowed in production CORS - review security")


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


# Export commonly used settings
def get_database_settings() -> DatabaseSettings:
    """Get database settings."""
    return get_settings().database


def get_security_settings() -> SecuritySettings:
    """Get security settings."""
    return get_settings().security


def get_app_settings() -> ApplicationSettings:
    """Get application settings."""
    return get_settings().app