"""Тесты POST /api/Auth/signup."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict

import pytest
import requests
from faker import Faker

HTTP_OK = 200
HTTP_CONFLICT = 409
HTTP_TOO_MANY_REQUESTS = 429
HTTP_UNSUPPORTED_MEDIA_TYPE = 415

EMAIL_ERROR_CODES = (
    "user.email.isRequired",
    "user.email.isInvalid",
    "user.email.notNull",
)

VALIDATION_ERROR_STATUSES = (HTTP_CONFLICT,)


def _parse_nested_json(payload: Any) -> Dict[str, Any]:
    """Разворачивает дважды закодированный JSON от сервера."""
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise AssertionError(
            "Expected JSON object after unwrapping, got "
            f"{type(payload).__name__}"
        )
    return payload


class TestAuthSignup:
    """Тесты эндпоинта /api/Auth/signup."""

    def test_signup_with_valid_email_returns_token(
        self,
        api_session: requests.Session,
        signup_url: str,
        valid_signup_payload: Dict[str, Any],
        request_timeout: int,
    ) -> None:
        """Валидный signup возвращает 200 и token."""
        response = api_session.post(
            signup_url,
            json=valid_signup_payload,
            timeout=request_timeout,
        )

        assert response.status_code == HTTP_OK, response.text
        assert (
            response.text and response.text.strip()
        ), "Signup response body must not be empty"

        content_type = response.headers.get("Content-Type", "")
        assert content_type.startswith(
            "application/json"
        ), f"Unexpected Content-Type: {content_type!r}"

        data = _parse_nested_json(response.json())

        assert data.get("email") == valid_signup_payload["email"], (
            f"Response email mismatch: {data.get('email')!r} != "
            f"{valid_signup_payload['email']!r}"
        )
        token = data.get("token")
        assert (
            isinstance(token, str) and token
        ), f"Expected non-empty 'token' string, got {token!r}"

    @pytest.mark.parametrize(
        "invalid_email",
        [
            pytest.param("", id="empty-string"),
            pytest.param("plainaddress", id="no-at-sign"),
            pytest.param("missing-at-sign.com", id="no-local-part"),
            pytest.param("@no-local-part.com", id="empty-local-part"),
            pytest.param("user@", id="empty-domain"),
            pytest.param("user@domain", id="no-tld"),
            pytest.param("user name@example.com", id="space-in-local-part"),
            pytest.param("user@@example.com", id="double-at"),
            pytest.param("user@.com", id="leading-dot-in-domain"),
        ],
    )
    def test_signup_with_invalid_email_is_rejected(
        self,
        api_session: requests.Session,
        signup_url: str,
        invalid_email: str,
        request_timeout: int,
    ) -> None:
        """Невалидный email отклоняется с 409 и кодом ошибки."""
        response = api_session.post(
            signup_url,
            json={"email": invalid_email},
            timeout=request_timeout,
        )

        assert response.status_code in VALIDATION_ERROR_STATUSES, (
            f"Unexpected status for email={invalid_email!r}: "
            f"{response.status_code}, body={response.text!r}"
        )

        body = response.json()
        assert "error" in body, f"Missing 'error' key: {body!r}"
        error = body["error"]
        assert (
            "code" in error and "message" in error
        ), f"Incomplete error object: {error!r}"
        assert error["code"] in EMAIL_ERROR_CODES, (
            f"Unexpected error code for email={invalid_email!r}: "
            f"{error['code']!r}"
        )

    def test_signup_without_email_field_is_rejected(
        self,
        api_session: requests.Session,
        signup_url: str,
        request_timeout: int,
    ) -> None:
        """Отсутствие обязательного поля email отклоняется."""
        response = api_session.post(
            signup_url, json={"lang": "en"}, timeout=request_timeout
        )

        assert response.status_code in VALIDATION_ERROR_STATUSES, response.text
        assert response.json()["error"]["code"] in EMAIL_ERROR_CODES

    def test_signup_with_empty_body_is_rejected(
        self,
        api_session: requests.Session,
        signup_url: str,
        request_timeout: int,
    ) -> None:
        """Пустое JSON-тело отклоняется."""
        response = api_session.post(
            signup_url, json={}, timeout=request_timeout
        )

        assert response.status_code in VALIDATION_ERROR_STATUSES, response.text
        assert response.json()["error"]["code"] in EMAIL_ERROR_CODES

    def test_signup_with_malformed_body_is_rejected(
        self,
        api_session: requests.Session,
        signup_url: str,
        request_timeout: int,
    ) -> None:
        """Не-JSON тело отклоняется с 415 или 409."""
        response = api_session.post(
            signup_url,
            data="not-a-json",
            headers={"Content-Type": "text/plain"},
            timeout=request_timeout,
        )

        assert response.status_code in (
            HTTP_UNSUPPORTED_MEDIA_TYPE,
            HTTP_CONFLICT,
        ), response.text

    def test_signup_with_duplicate_email_is_throttled(
        self,
        api_session: requests.Session,
        signup_url: str,
        unique_email: str,
        request_timeout: int,
    ) -> None:
        """Повторный signup того же email throttled'ится (429)."""
        payload = {"email": unique_email, "lang": "en"}

        first = api_session.post(
            signup_url, json=payload, timeout=request_timeout
        )
        assert first.status_code == HTTP_OK, first.text

        second = api_session.post(
            signup_url, json=payload, timeout=request_timeout
        )
        assert second.status_code == HTTP_TOO_MANY_REQUESTS, (
            f"Second signup for the same email must be throttled "
            f"(got {second.status_code}). Body: {second.text!r}"
        )
        assert (
            second.json()["error"]["code"] == "user.signup.resetTokenSent"
        ), second.text

    @pytest.mark.xfail(
        reason=(
            "Server regex allows consecutive dots in the domain "
            "(user@example..com is accepted). Test asserts the "
            "desired behaviour; remove the marker once fixed."
        ),
        strict=True,
    )
    def test_signup_double_dot_domain_is_rejected(
        self,
        api_session: requests.Session,
        signup_url: str,
        request_timeout: int,
    ) -> None:
        """Две точки подряд в домене должны отклоняться."""
        local = uuid.uuid4().hex
        quirky_email = f"{local}@example..com"

        response = api_session.post(
            signup_url,
            json={"email": quirky_email},
            timeout=request_timeout,
        )

        assert (
            response.status_code in VALIDATION_ERROR_STATUSES
        ), f"Server accepted {quirky_email!r} — regex is too permissive"

    def test_signup_with_utm_payload_succeeds(
        self,
        api_session: requests.Session,
        signup_url: str,
        faker_instance: Faker,
        request_timeout: int,
    ) -> None:
        """Необязательное поле utm принимается как есть."""
        payload = {
            "email": faker_instance.unique.email(),
            "lang": "en",
            "utm": '{"utm_source":"google","utm_medium":"cpc"}',
        }
        response = api_session.post(
            signup_url, json=payload, timeout=request_timeout
        )
        assert response.status_code == HTTP_OK, response.text

    @pytest.mark.xfail(
        reason=(
            "Swagger declares additionalProperties:false, but the "
            "server silently ignores unknown JSON fields. Test "
            "asserts the documented contract; remove the marker "
            "once the server enforces it."
        ),
        strict=True,
    )
    def test_signup_with_unknown_field_is_rejected(
        self,
        api_session: requests.Session,
        signup_url: str,
        unique_email: str,
        request_timeout: int,
    ) -> None:
        """Неизвестное поле должно отклоняться по Swagger."""
        payload = {"email": unique_email, "unknown_field": "boom"}
        response = api_session.post(
            signup_url, json=payload, timeout=request_timeout
        )

        assert response.status_code in VALIDATION_ERROR_STATUSES, (
            f"Unknown field silently ignored "
            f"(status={response.status_code})"
        )

    def test_signup_with_text_json_content_type(
        self,
        api_session: requests.Session,
        signup_url: str,
        valid_signup_payload: Dict[str, Any],
        request_timeout: int,
    ) -> None:
        """Content-Type text/json поддерживается по Swagger."""
        response = api_session.post(
            signup_url,
            json=valid_signup_payload,
            headers={"Content-Type": "text/json"},
            timeout=request_timeout,
        )

        assert response.status_code == HTTP_OK, (
            f"Swagger declares text/json support, but got "
            f"{response.status_code}: {response.text!r}"
        )
