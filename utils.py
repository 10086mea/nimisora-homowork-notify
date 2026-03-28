# utils.py

import hashlib

def md5(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()
