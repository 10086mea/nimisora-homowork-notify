# data_fetch.py
import aiohttp
import asyncio
import time
import requests
import json
from requests.exceptions import RequestException, JSONDecodeError
from typing import Dict, List, Any

def fetch_semester_info(session, base_url, jsessionid):
    """获取学期信息"""
    semester_url = f"{base_url}/back/rp/common/teachCalendar.shtml?method=queryCurrentXq"
    headers = {"cookies": jsessionid}
    semester_response = session.get(semester_url, headers=headers)
    if semester_response.status_code == 200:
        semester_data = semester_response.json()
        semester = semester_data["result"][0]
        semester_info = {
            "学期名称": semester["xqName"],
            "学期代码": semester["xqCode"],
            "开始日期": semester["beginDate"],
            "结束日期": semester["endDate"],
            "是否当前学期": semester["currentFlag"]
        }
        print("学期信息:", semester_info)
        return semester_info
    else:
        raise Exception("获取学期信息失败。")

def fetch_user_info(session, base_url, jsessionid):
    """获取用户信息"""
    user_info_url = f"{base_url}/back/coursePlatform/userInfo.shtml?method=getUserInfo"
    headers = {"cookies": jsessionid}
    user_info_response = session.get(user_info_url, headers=headers)
    if user_info_response.status_code == 200:
        user_info_data = user_info_response.json()
        user_info = user_info_data.get("userInfo", {})
        user_info_dict = {
            "学生编号": user_info.get("STU_NO"),
            "姓名": user_info.get("STU_NAME"),
            "邮箱": f"{user_info.get('STU_NO')}@bjtu.edu.cn",
            "学院": user_info.get("SCHOOL"),
            "专业": user_info.get("PROFESSION"),
            "年级": user_info.get("GRADE_NAME"),
            "班级": user_info.get("CLASS_NAME")
        }
        print("用户信息:", user_info_dict)
        return user_info_dict
    else:
        raise Exception("获取用户信息失败。")

def fetch_course_list(session, base_url, jsessionid, xq_code):
    """获取课程列表"""
    course_list_url = f"{base_url}/back/coursePlatform/course.shtml?method=getCourseList&pagesize=100&page=1&xqCode={xq_code}"
    headers = {"cookies": jsessionid}
    course_list_response = session.get(course_list_url, headers=headers)
    if course_list_response.status_code == 200:
        course_list_data = course_list_response.json()
        courses = course_list_data.get("courseList", [])
        print("课程列表:")
        for course in courses:
            print(f"课程名称: {course.get('name')}, 课程ID: {course.get('id')}, 课程代码: {course.get('course_num')}, 教师: {course.get('teacher_name')}, 开始日期: {course.get('begin_date')}, 结束日期: {course.get('end_date')}")
        return courses
    else:
        raise Exception("获取课程列表失败。")


async def create_async_session(sync_session: requests.Session) -> aiohttp.ClientSession:
    """从同步session创建异步session"""
    cookies = {k: v for k, v in sync_session.cookies.items()}
    headers = dict(sync_session.headers)

    return aiohttp.ClientSession(
        cookies=cookies,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=300)
    )


async def fetch_homework_data_for_course(
        course_name: str,
        url: str,
        session: aiohttp.ClientSession,
        retries: int = 0,
        max_retries: int = 3,
        backoff_factor: int = 1,
        subType: int=0
) -> List[Dict[str, Any]]:
    """发送异步请求并获取作业数据，带重试机制"""
    try:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"HTTP状态码: {response.status}")

            # 读取响应内容
            content = await response.text()
            homework_data = json.loads(content)

            # 提取所需的作业信息
            formatted_homeworks = []
            for homework in homework_data.get("courseNoteList", []):
                homework_info = {
                    "作业ID":homework.get("id"),
                    "作业标题": homework.get("title"),
                    "创建日期": homework.get("create_date"),
                    "开放时间": homework.get("open_date"),
                    "结束时间": homework.get("end_time"),
                    "提交状态": homework.get("subStatus"),
                    "分数": homework.get("stu_score")
                }
                formatted_homeworks.append(homework_info)
            homework_types = {
                0: "普通作业",
                1: "课程报告",
                2: "实验作业"
            }
            print(f"[{course_name}] {homework_types[subType]}获取完成")
            if(formatted_homeworks):
                print(f"获取到{formatted_homeworks}")
            return formatted_homeworks

    except (aiohttp.ClientError, JSONDecodeError, Exception) as e:
        retries += 1
        if retries < max_retries:
            print(f"请求失败，第 {retries} 次重试，课程：{course_name} 错误: {e}")
            await asyncio.sleep(backoff_factor * retries)  # 等待后重试
            return await fetch_homework_data_for_course(
                course_name, url, session, retries, max_retries, backoff_factor
            )
        else:
            print(f"请求失败，已达到最大重试次数 ({max_retries})，课程：{course_name}，错误: {e}")
            return []


async def fetch_homework_data(
        sync_session: requests.Session,
        base_url: str,
        course_list: List[Dict[str, Any]],
        user_info: Dict[str, Any]
) -> str:
    """获取所有课程的作业数据"""
    all_courses_homework_data = {}

    # 创建异步session
    async with await create_async_session(sync_session) as async_session:
        # 使用异步任务并发处理
        tasks = []
        for course in course_list:
            course_name = course['name']
            course_id = course['id']

            # 定义不同类型作业的URL subType 0:作业 1:课程报告 2:实验
            homework_types = [
                (subType,f"{base_url}/back/coursePlatform/homeWork.shtml?method=getHomeWorkList&cId={course_id}&subType={subType}&page=1&pagesize=100")
                for subType in range(3)
            ]

            # 为每个课程和作业类型创建异步任务
            course_tasks = [
                fetch_homework_data_for_course(course_name, url, async_session,subType=subType)
                for subType, url in homework_types
            ]
            tasks.extend(course_tasks)

        # 批量运行异步任务
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for i, course in enumerate(course_list):
            course_name = course['name']
            # 获取当前课程的3个任务结果
            course_results = all_results[i * 3:(i + 1) * 3]

            # 合并当前课程的所有作业数据
            valid_results = []
            for result in course_results:
                if isinstance(result, list):  # 确保结果不是异常
                    valid_results.extend(result)

            if valid_results:
                all_courses_homework_data[course_name] = valid_results
            else:
                print(f"课程 {course_name} 无作业数据")

    # 转换为JSON格式
    return json.dumps(all_courses_homework_data, ensure_ascii=False, indent=4)
