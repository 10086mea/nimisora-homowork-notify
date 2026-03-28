# services/notification_service.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
import os
from datetime import datetime

from config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM_ADDRESS

# Setup Jinja2 environment
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
loader = FileSystemLoader(os.path.join(project_root, 'templates'))
env = Environment(loader=loader)

def send_email(to_address, subject, template_name, **kwargs):
    template = env.get_template(template_name)
    # Add 'now' and 'user' to the template context
    kwargs['now'] = datetime.now()
    html_body = template.render(**kwargs)

    msg = MIMEMultipart()
    msg['From'] = MAIL_FROM_ADDRESS
    msg['To'] = to_address
    msg['Subject'] = subject

    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Successfully sent email to {to_address}")
    except Exception as e:
        print(f"Failed to send email to {to_address}: {e}")
