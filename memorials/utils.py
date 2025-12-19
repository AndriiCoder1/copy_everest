import string
import secrets

def generate_short_code(length=8):
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
