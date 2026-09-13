"""Utilities for bill_variance_domain."""

import os
import hmac
import hashlib
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

FERNET_KEY = os.environ["FERNET_KEY"]
HMAC_SECRET = os.environ["HMAC_SECRET"].encode()


def hash_ban(ban: str) -> str:
    """
    Create a deterministic BAN hash suitable for storage and lookup.
    """
    return hmac.new(
        HMAC_SECRET,
        ban.strip().encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def create_idempotent_key(account_id: str, campaign_code: str, date_stamp: str) -> str:
    """
    Creates a deterministic, non-plain-text, <40 char transaction/idempotency ID.
    Same inputs ALWAYS produce the exact same output string.
    """
    
    MASTER_KEY = base64.b64decode(FERNET_KEY)
    
    if (campaign_code == "PENDING_CREDITS"):
        campaign_code = "PNDGCR"
    elif (campaign_code == "PROMOTION_EXPIRY"):
        campaign_code == "PROMEX"
    
    # 1. Derive a deterministic 4-byte nonce from the input parameters
    seed = f"{account_id}:{campaign_code}:{date_stamp}".encode('utf-8')
    nonce = hashlib.sha256(seed).digest()[:4]
    
    # 2. Build full 16-byte counter block for AES-CTR
    full_counter = nonce + b"\x00" * 12

    # 3. Encrypt the account_id
    cipher = Cipher(
        algorithms.AES(MASTER_KEY), 
        modes.CTR(full_counter), 
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(account_id.encode('utf-8')) + encryptor.finalize()

    # 4. Combine nonce + ciphertext and encode to URL-safe Base64
    combined = nonce + ciphertext
    token = base64.urlsafe_b64encode(combined).decode('utf-8').rstrip('=')

    # 5. Format key with campaign prefix (max 6 chars)
    clean_prefix = campaign_code[:6].lower().replace("_", "")
    return f"{clean_prefix}_{token}"