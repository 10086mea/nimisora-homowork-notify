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

def fetch_homework_data(session, base_url, course_list, user_info):
    """获取所有课程的作业数据"""
    all_courses_homework_data = {}


    # 遍历所有课程
    for course in course_list:
        course_name = course['name']
        homework_url = f"{base_url}/back/coursePlatform/homeWork.shtml?method=getHomeWorkList&cId={course['id']}&subType=0&page=1&pagesize=100"

        homework_response = session.get(homework_url)

        if homework_response.status_code == 200:
            homework_data = homework_response.json()
            homeworks = homework_data.get("courseNoteList", [])

            course_homeworks = []
            for homework in homeworks:
                homework_info = {
                    "作业标题": homework.get("title"),
                    "创建日期": homework.get("create_date"),
                    "开放时间": homework.get("open_date"),
                    "结束时间": homework.get("end_time"),
                    "提交状态": homework.get("subStatus"),
                    "分数": homework.get("stu_score")
                }
                course_homeworks.append(homework_info)



            all_courses_homework_data[course_name] = course_homeworks
        else:
            print(f"获取课程 {course_name} 的作业信息失败")



    all_courses_homework_json = json.dumps(all_courses_homework_data, ensure_ascii=False, indent=4)
    return all_courses_homework_json
