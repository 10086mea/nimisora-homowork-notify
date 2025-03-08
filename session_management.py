import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from utils import md5
import time
from config import DEFAULT_PASSWORD_PREFIX
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


class PasswordError(Exception):
    """密码错误或密码锁定"""
    def __init__(self, message, is_locked=False):
        self.message = message
        self.is_locked = is_locked  # 标记是否因密码错误次数过多被锁定
        super().__init__(self.message)
def perform_login(session, base_url, student_id, jsessionid, captcha,user, max_retries=3, retry_delay=2):
    """
    使用学号和验证码进行登录。
    :param session: requests.Session 对象
    :param base_url: 基础 URL
    :param student_id: 学号
    :param jsessionid: 会话 ID
    :param captcha: 验证码
    :param user 主要用来传入confirmed并进行修改
    :param max_retries: 最大重试次数
    :param retry_delay: 重试间隔时间（秒）
    """
    login_url = f"{base_url}/s.shtml"
    password = user["password"]
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "cookies": jsessionid
    }
    if password == "default":
        md5_password = md5(DEFAULT_PASSWORD_PREFIX+student_id)
    else:
        md5_password = password
    data = {
        "username": student_id,
        "password": md5_password,
        "passcode": captcha
    }

    for attempt in range(max_retries):
        try:
            response = session.post(login_url, data=data, headers=headers, allow_redirects=True)
            print("已发送登录请求，状态码:", response.status_code)

            if response.status_code == 200:
                # 解码响应内容
                content = response.content.decode('gbk')
                print(content)
                # 检查是否包含错误信息
                if "alert('" in content:
                    # 提取alert中的错误信息
                    error_msg = content.split("alert('")[1].split("');")[0]
                    if "密码输入错误次数过多" in error_msg:
                        user["confirmed"] = -1
                        raise PasswordError(error_msg, is_locked=True)
                    elif "账号或密码错误" in error_msg:
                        user["confirmed"] = -1
                        raise PasswordError(error_msg, is_locked=False)
                    else:
                        user["confirmed"] = -1
                        raise PasswordError(error_msg)
                else:
                    print("登录成功")

                    print(content)
                    return response
            else:
                content = response.content.decode('gbk')
                print(content)
                print(f"请求失败，状态码: {response.status_code}，尝试第 {attempt + 1} 次。")
        except requests.RequestException as e: #仅捕获网络相关异常，密码异常继续抛出
            print(f"发生异常: {e}，尝试第 {attempt + 1} 次。")

        # 如果还没达到最大重试次数，等待一段时间再重试
        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    # 如果到达这里，说明所有尝试都失败
    raise Exception("登录请求失败，已达到最大重试次数。")
