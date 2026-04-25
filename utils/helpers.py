import hashlib
import secrets


def generate_token() -> str:
    """Generate unique link token for user."""
    return secrets.token_urlsafe(12)


def hash_sender(sender_id: int, receiver_id: int) -> str:
    """Create anonymous hash for sender — same sender always gets same hash per receiver."""
    raw = f"{sender_id}:{receiver_id}:anonmsg_salt_v1"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
