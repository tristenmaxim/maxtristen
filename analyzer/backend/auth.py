import os
import re
import secrets
import time
from typing import Optional
from urllib.parse import urlparse

from eth_account import Account
from eth_account.messages import encode_defunct

import db

ALLOWED_WALLETS = {
    w.strip().lower() for w in os.getenv("ANALYZER_ALLOWED_WALLETS", "").split(",") if w.strip()
}

SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://maxtristen.com")
SITE_DOMAIN = urlparse(SITE_BASE_URL).netloc
COOKIE_SECURE = SITE_BASE_URL.startswith("https")

SESSION_TTL_SECONDS = 30 * 24 * 3600
NONCE_TTL_SECONDS = 5 * 60
LINK_CODE_TTL_SECONDS = 10 * 60

_nonces: dict[str, float] = {}
_link_codes: dict[str, tuple[str, float]] = {}


def _purge_expired(store: dict, now: float) -> None:
    expired = [k for k, v in store.items() if (v if isinstance(v, float) else v[1]) < now]
    for k in expired:
        del store[k]


def issue_nonce() -> str:
    now = time.time()
    _purge_expired(_nonces, now)
    nonce = secrets.token_hex(16)
    _nonces[nonce] = now + NONCE_TTL_SECONDS
    return nonce


def consume_nonce(nonce: str) -> bool:
    expires = _nonces.pop(nonce, None)
    return expires is not None and expires >= time.time()


SIWE_FIELD_RE = re.compile(r"^(?P<key>[A-Za-z ]+):\s*(?P<value>.*)$")


def _parse_siwe_message(message: str) -> dict:
    lines = message.splitlines()
    if not lines:
        raise ValueError("empty message")
    header_match = re.match(r"^(?P<domain>.+) wants you to sign in with your Ethereum account:$", lines[0])
    if not header_match:
        raise ValueError("malformed SIWE header")
    fields = {"domain": header_match.group("domain")}
    if len(lines) > 1:
        fields["address"] = lines[1].strip()
    for line in lines[2:]:
        m = SIWE_FIELD_RE.match(line)
        if m:
            fields[m.group("key").strip()] = m.group("value").strip()
    return fields


def verify_siwe(message: str, signature: str) -> str:
    fields = _parse_siwe_message(message)

    if fields.get("domain") != SITE_DOMAIN:
        raise ValueError("domain mismatch")

    nonce = fields.get("Nonce")
    if not nonce or not consume_nonce(nonce):
        raise ValueError("invalid or expired nonce")

    signable = encode_defunct(text=message)
    recovered = Account.recover_message(signable, signature=signature)
    return recovered.lower()


def create_session(wallet_address: str) -> str:
    token = secrets.token_urlsafe(32)
    db.create_session(token, wallet_address, ttl_seconds=SESSION_TTL_SECONDS)
    return token


def require_wallet_from_cookie(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    wallet = db.get_session(token)
    if wallet is None or wallet not in ALLOWED_WALLETS:
        return None
    return wallet


def issue_link_code(wallet_address: str) -> str:
    now = time.time()
    _purge_expired(_link_codes, now)
    code = secrets.token_hex(4).upper()
    _link_codes[code] = (wallet_address, now + LINK_CODE_TTL_SECONDS)
    return code


def consume_link_code(code: str) -> Optional[str]:
    entry = _link_codes.pop(code.strip().upper(), None)
    if entry is None:
        return None
    wallet, expires = entry
    if expires < time.time():
        return None
    return wallet
