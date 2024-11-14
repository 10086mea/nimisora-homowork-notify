import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from utils import md5

def initialize_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504)):
    """初始化带重试机制的会话。"""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def initialize_session(base_url):
    """初始化会话并获取初始的cookie和JSESSIONID。"""
    session = initialize_retry_session()
    captcha_url_png = f"{base_url}/GetImg"

    # 获取初始cookie
    response = session.get(base_url)
    session.get(captcha_url_png)
    if response.status_code == 200:
        print("已获取初始cookie。")
        jsessionid = session.cookies.get('JSESSIONID')
        if jsessionid:
            print("已获取JSESSIONID:", jsessionid)
            return session, jsessionid
        else:
            raise Exception("在cookie中未找到JSESSIONID。")
    else:
        raise Exception("获取初始cookie失败。")

def get_captcha(session, base_url):
    """获取验证码。"""
    captcha_url_png = f"{base_url}/GetImg"
    session.get(captcha_url_png)
    captcha_url = f"{base_url}/confirmImg"
    response = session.get(captcha_url)
    if response.status_code == 200 and response.text:
        captcha = response.text
        print("已获取验证码:", captcha)
        return captcha
    else:
        raise Exception("获取验证码失败。")

def perform_login(session, base_url, student_id, jsessionid, captcha):
    """使用学号和验证码进行登录。"""
    login_url = f"{base_url}/s.shtml"
    password = f"Bjtu@{student_id}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "cookies": jsessionid
    }
    data = {
        "username": student_id,
        "password": md5(password),
        "passcode": captcha
    }
    response = session.post(login_url, data=data, headers=headers, allow_redirects=True)
    print("已发送登录请求，状态码:", response.status_code)
    if response.status_code == 200:
        print("登录成功。")
    else:
        raise Exception("登录失败。")
