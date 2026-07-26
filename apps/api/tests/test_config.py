"""Tests for app configuration and database URL normalization."""

import pytest
from app.config import _normalize_asyncpg_url, Settings


def test_normalize_asyncpg_url_postgres_scheme():
    assert _normalize_asyncpg_url("postgres://user:pass@localhost:5432/db") == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_normalize_asyncpg_url_postgresql_scheme():
    assert _normalize_asyncpg_url("postgresql://user:pass@localhost:5432/db") == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_normalize_asyncpg_url_sslmode_conversion():
    url = "postgres://user:pass@host.aivencloud.com:5432/defaultdb?sslmode=require"
    expected = "postgresql+asyncpg://user:pass@host.aivencloud.com:5432/defaultdb?ssl=require"
    assert _normalize_asyncpg_url(url) == expected


def test_normalize_asyncpg_url_multiple_query_params():
    url = "postgresql://user:pass@host:5432/db?channel_binding=disable&sslmode=require"
    expected = "postgresql+asyncpg://user:pass@host:5432/db?channel_binding=disable&ssl=require"
    assert _normalize_asyncpg_url(url) == expected


def test_settings_database_url_validation():
    s = Settings(database_url="postgres://user:pass@host:5432/db?sslmode=require")
    assert s.database_url == "postgresql+asyncpg://user:pass@host:5432/db?ssl=require"
