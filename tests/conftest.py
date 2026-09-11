"""Pytest fixtures shared across the Auth signup test suite."""

from __future__ import annotations

import uuid
from typing import Generator

import pytest
import requests
from faker import Faker

BASE_URL: str = "https://automation.tivaliclub.com/fcle"
SIGNUP_ENDPOINT: str = "/api/Auth/signup"
DEFAULT_TIMEOUT: int = 15


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def request_timeout() -> int:
    return DEFAULT_TIMEOUT


@pytest.fixture(scope="session")
def api_session() -> Generator[requests.Session, None, None]:
    with requests.Session() as session:
        session.headers["Accept"] = "application/json"
        yield session


@pytest.fixture(scope="session")
def faker_instance() -> Faker:
    return Faker()


@pytest.fixture()
def unique_email(faker_instance: Faker) -> str:
    return f"test_{uuid.uuid4().hex}@{faker_instance.domain_name()}"


@pytest.fixture()
def signup_url(base_url: str) -> str:
    return f"{base_url}{SIGNUP_ENDPOINT}"


@pytest.fixture()
def valid_signup_payload(unique_email: str) -> dict:
    return {"email": unique_email, "lang": "en"}
