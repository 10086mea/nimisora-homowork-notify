# utils.py

import hashlib

def md5(text):
    """返回文本的MD5值."""
    return hashlib.md5(text.encode()).hexdigest()
