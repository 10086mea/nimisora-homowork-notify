# data_fetch.py

import json


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
import time
import requests
import json
from requests.exceptions import RequestException, JSONDecodeError

def fetch_homework_data(session, base_url, course_list, user_info, max_retries=3, backoff_factor=1):
    """获取所有课程的作业数据，带重试机制"""
    all_courses_homework_data = {}

    def fetch_homework_data_for_course(course_name, url, retries):
        """发送请求并获取作业数据，带重试机制"""
        while retries < max_retries:
            try:
                response = session.get(url)
                response.raise_for_status()  # 如果响应码不是200，抛出异常

                # 尝试解析 JSON
                homework_data = response.json()
                return homework_data.get("courseNoteList", [])
            except (RequestException, JSONDecodeError) as e:
                retries += 1
                if retries < max_retries:
                    print(f"请求失败，第 {retries} 次重试，课程：{course_name} 错误: {e}")
                    time.sleep(backoff_factor * retries)  # 等待后重试
                else:
                    print(f"请求失败，已达到最大重试次数 ({max_retries})，课程：{course_name}，错误: {e}")
                    return []  # 如果达到最大重试次数，返回空列表

    # 遍历所有课程
    for course in course_list:
        course_name = course['name']

        # 定义不同类型作业的URL
        homework_url_0 = f"{base_url}/back/coursePlatform/homeWork.shtml?method=getHomeWorkList&cId={course['id']}&subType=0&page=1&pagesize=100"
        homework_url_1 = f"{base_url}/back/coursePlatform/homeWork.shtml?method=getHomeWorkList&cId={course['id']}&subType=1&page=1&pagesize=100"
        homework_url_2 = f"{base_url}/back/coursePlatform/homeWork.shtml?method=getHomeWorkList&cId={course['id']}&subType=2&page=1&pagesize=100"

        # 获取不同类型的作业数据
        course_homeworks = []

        # 获取作业类型 0（普通作业）
        homeworks_0 = fetch_homework_data_for_course(course_name, homework_url_0, retries=0)
        for homework in homeworks_0:
            homework_info = {
                "作业标题": homework.get("title"),
                "创建日期": homework.get("create_date"),
                "开放时间": homework.get("open_date"),
                "结束时间": homework.get("end_time"),
                "提交状态": homework.get("subStatus"),
                "分数": homework.get("stu_score")
            }
            course_homeworks.append(homework_info)

        # 获取作业类型 1（课程报告）
        homeworks_1 = fetch_homework_data_for_course(course_name, homework_url_1, retries=0)
        for homework in homeworks_1:
            homework_info = {
                "作业标题": homework.get("title"),
                "创建日期": homework.get("create_date"),
                "开放时间": homework.get("open_date"),
                "结束时间": homework.get("end_time"),
                "提交状态": homework.get("subStatus"),
                "分数": homework.get("stu_score")
            }
            course_homeworks.append(homework_info)

        # 获取作业类型 2（实验）
        homeworks_2 = fetch_homework_data_for_course(course_name, homework_url_2, retries=0)
        for homework in homeworks_2:
            homework_info = {
                "作业标题": homework.get("title"),
                "创建日期": homework.get("create_date"),
                "开放时间": homework.get("open_date"),
                "结束时间": homework.get("end_time"),
                "提交状态": homework.get("subStatus"),
                "分数": homework.get("stu_score")
            }
            course_homeworks.append(homework_info)

        # 将课程的作业数据添加到总数据字典中
        if course_homeworks:
            all_courses_homework_data[course_name] = course_homeworks
        else:
            print(f"课程 {course_name} 无作业数据")

    # 转换为 JSON 格式
    all_courses_homework_json = json.dumps(all_courses_homework_data, ensure_ascii=False, indent=4)
    return all_courses_homework_json

