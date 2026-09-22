from django.conf import settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

RECOVERY_TOKEN_SALT = 'abandoned-cart-recovery'
DEFAULT_TOKEN_MAX_AGE = 604800  # 7 days in seconds


def generate_cart_recovery_token(cart) -> str:
    """
    Generates a cryptographically signed, timestamped token embedding the cart ID
    and associated user ID. Excludes raw email to prevent PII leakage in URLs and logs.
    """
    signer = TimestampSigner(salt=RECOVERY_TOKEN_SALT)
    payload = {
        'cart_id': cart.id,
        'user_id': cart.user_id,
    }
    return signer.sign_object(payload)


def verify_cart_recovery_token(token: str, max_age: int = DEFAULT_TOKEN_MAX_AGE) -> dict:
    """
    Validates the cryptographic signature and timestamp of a recovery token.
    Raises BadSignature if the token is tampered with, or SignatureExpired if older than max_age.
    Returns the decoded dictionary payload on success.
    """
    signer = TimestampSigner(salt=RECOVERY_TOKEN_SALT)
    return signer.unsign_object(token, max_age=max_age)


def build_cart_recovery_url(token: str) -> str:
    """
    Constructs the absolute frontend recovery URL containing the signed token query parameter.
    """
    frontend_base = getattr(settings, 'FRONTEND_URL', 'https://yourstore.com').rstrip('/')
    return f"{frontend_base}/cart/recover/?token={token}"
