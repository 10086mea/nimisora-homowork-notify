# 介绍页
[上条当咩的blog](https://love.nimisora.icu/archives/371)
# 订阅页面
[新海天订阅页](https://love.nimisora.icu/homework-notify/)
# 功能介绍
- 将零点截止的作业-1s，截止日期显示改为前一晚23:59分
- 自动忽略已过期的作业
- 15min重新请求一次，和缓存的csv作业列表进行比对
- 每次作业紧急类型变化时发送一个提醒邮件，邮件内包含全部作业类型
# 邮件样式演示
![邮件](/Screenshot_2024-11-29-15-11-29-806_com.tencent.mo.jpg)
# 本地部署使用说明
目前支持两个阈值，一个常规推送，一个紧急推送。

- 需要修改 `config_template.py` 文件设置邮箱地址以及SMTP密码等内容，并重命名为 `config.py` 才能正常使用。
- 需要修改 `user_data.csv` 来修改订阅列表。

# 后续更新
- 可能还会接入到[校园论坛](https://bjtu.top)上吧，先摸了
