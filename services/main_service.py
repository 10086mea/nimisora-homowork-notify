# services/main_service.py

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from PIL import Image
import io
import aiohttp
import asyncio
import json
import os
import re
from sqlalchemy.orm import Session

from captcha.predict import load_model, predict_from_image
from config import BASE_URL, SESSION_URL, CAPTCHA_MODEL_PATH, DEFAULT_PASSWORD_PREFIX
from utils import md5
from models import User


def initialize_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504)):
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

def get_captcha_and_predict(session, model):
    captcha_url_png = f"{BASE_URL}/GetImg"
    response = session.get(captcha_url_png)
    if response.status_code == 200:
        image = Image.open(io.BytesIO(response.content))
        captcha_text = predict_from_image(model, image)
        return captcha_text
    else:
        raise Exception("Failed to download captcha image.")

def perform_login(session, student_id, md5_password, captcha):
    login_url = f"{BASE_URL}/s.shtml"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    data = {
        "username": student_id,
        "password": md5_password,
        "passcode": captcha
    }
    response = session.post(login_url, data=data, headers=headers, allow_redirects=True)
    decoded_content = response.content.decode('gbk')
    if "alert('" in decoded_content:
        error_msg = decoded_content.split("alert('")[1].split("');")[0]
        raise Exception(f"Login failed: {error_msg}")
    return session

def get_session_id(session):
    response = session.get(SESSION_URL)
    if response.status_code == 200:
        return response.json()['sessionId']
    else:
        raise Exception("Failed to get session id.")

def _fetch_and_update_password(db: Session, user: User, session: requests.Session):
    """
    Internal function for passwordless login and updating the password in the DB.
    """
    print(f"[登录服务] 用户 {user.student_id} 触发免密登录并获取密码流程...")
    try:
        # Step 1: Passwordless login
        passwordless_url = f"{BASE_URL}/s.shtml?username={user.student_id}&loginType=2&login=main_2"
        response = session.get(passwordless_url, allow_redirects=True)
        response.raise_for_status()
        print(f"[登录服务] 免密登录请求成功。")

        # Step 2: Get sessionId
        session_id = get_session_id(session)
        jsessionid = session.cookies.get('JSESSIONID')
        print(f"[登录服务] 获取到 Session ID: {session_id}")

        # Step 3: Go to personal center and get password
        personal_center_url = f"{BASE_URL}/back/personalCenter/personalCenter.shtml?method=toPersonalCenter&sessionId={session_id}&pageToType=2"
        headers = {"cookies": jsessionid, "sessionId": session_id}
        pc_response = session.get(personal_center_url, headers=headers)
        pc_response.raise_for_status()
        
        html_content = pc_response.text
        match = re.search(r'<input[^>]+id="odbcPassword"[^>]+value="([^"]+)"', html_content)
        
        if not match:
            raise Exception("无法在个人中心页面找到密码MD5值。")

        password_md5 = match.group(1)
        print(f"[登录服务] 成功从页面获取密码MD5: {password_md5}")

        # Step 4: Update user in DB
        user.password_md5 = password_md5
        db.commit()
        print(f"[登录服务] 密码MD5已更新到数据库。")
        
        # The session should be authenticated, return it
        return session, jsessionid, session_id

    except Exception as e:
        print(f"[登录服务] 免密登录或密码获取失败: {e}")
        raise # Re-raise the exception to be caught by the crawler task

def login(db: Session, user: User):
    print(f"[登录服务] 开始为用户 {user.student_id} 处理登录...")
    session = initialize_retry_session()

    # If user has no password or it's 'undefined', use the passwordless flow first.
    if not user.password_md5 or user.password_md5 == 'undefined':
        return _fetch_and_update_password(db, user, session)

    # Otherwise, try to log in with the existing password.
    else:
        print(f"[登录服务] 用户 {user.student_id} 有密码，执行标准验证码登录...")
        try:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            model_path = os.path.join(project_root, CAPTCHA_MODEL_PATH)
            captcha_model = load_model(model_path)
            captcha = get_captcha_and_predict(session, captcha_model)
            
            password_to_use = user.password_md5
            if password_to_use == 'default':
                password_to_use = md5(DEFAULT_PASSWORD_PREFIX + user.student_id)

            session = perform_login(session, user.student_id, password_to_use, captcha)
            
            session_id = get_session_id(session)
            jsessionid = session.cookies.get('JSESSIONID')
            return session, jsessionid, session_id
        except Exception as e:
            # If login fails due to wrong password, try the recovery flow.
            if "账号或密码错误" in str(e):
                print(f"[登录服务] 登录失败: {e}。尝试自动获取新密码...")
                return _fetch_and_update_password(db, user, session)
            else:
                # For other errors (captcha, network, etc.), just re-raise.
                raise e

def fetch_semester_info(session, jsessionid):
    semester_url = f"{BASE_URL}/back/rp/common/teachCalendar.shtml?method=queryCurrentXq"
    headers = {"cookies": jsessionid}
    semester_response = session.get(semester_url, headers=headers)
    if semester_response.status_code == 200:
        return semester_response.json()["result"][0]
    else:
        raise Exception("Failed to fetch semester info.")

def fetch_user_info(session, jsessionid):
    user_info_url = f"{BASE_URL}/back/coursePlatform/userInfo.shtml?method=getUserInfo"
    headers = {"cookies": jsessionid}
    user_info_response = session.get(user_info_url, headers=headers)
    if user_info_response.status_code == 200:
        return user_info_response.json()["userInfo"]
    else:
        raise Exception("Failed to fetch user info.")

def fetch_course_list(session, jsessionid, xq_code, sessionId):
    course_list_url = f"{BASE_URL}/back/coursePlatform/course.shtml?method=getCourseList&pagesize=100&page=1&xqCode={xq_code}"
    headers = {"cookies": jsessionid, "sessionId": sessionId}
    course_list_response = session.get(course_list_url, headers=headers)
    if course_list_response.status_code == 200:
        return course_list_response.json()["courseList"]
    else:
        raise Exception("Failed to fetch course list.")

async def fetch_homework_data_for_course(session, course_id, sub_type, sessionId, jsessionid):
    url = f"{BASE_URL}/back/coursePlatform/homeWork.shtml?method=getHomeWorkList&cId={course_id}&subType={sub_type}&page=1&pagesize=100"
    headers = {"cookies": jsessionid, "sessionId": sessionId}
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type or 'text/json' in content_type:
                return await response.json(content_type=None)
            else:
                text = await response.text()
                raise Exception(f"Unexpected content type: {response.headers.get('Content-Type')}. Content: {text[:200]}")
        else:
            return None

async def fetch_all_homework_data(sync_session, course_list, sessionId, jsessionid):
    cookies = {c.name: c.value for c in sync_session.cookies}
    homework_by_course = {}
    async with aiohttp.ClientSession(cookies=cookies) as async_session:
        for course in course_list:
            tasks = []
            for sub_type in range(3):
                tasks.append(fetch_homework_data_for_course(async_session, course['id'], sub_type, sessionId, jsessionid))
            results = await asyncio.gather(*tasks)
            
            course_homeworks = []
            for result in results:
                if result and 'courseNoteList' in result:
                    course_homeworks.extend(result['courseNoteList'])
            
            if course_homeworks:
                homework_by_course[course['name']] = course_homeworks
                
    return homework_by_course