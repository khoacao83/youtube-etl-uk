"""Cấu hình cho YouTube ETL UK."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENV: str = "dev"
    GCP_PROJECT: str = "youtube-etl-uk"
    BQ_LOCATION: str = "asia-southeast1"
    BQ_RAW_DATASET: str = "yt_uk_dev_raw"
    BQ_CLEAN_DATASET: str = "yt_uk_dev_clean"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()