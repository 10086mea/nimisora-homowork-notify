# web_ui/app.py

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import User, Homework
from config import DATABASE_URL

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = 'a_secret_key_for_flashing_messages' # Required for flash messages
db = SQLAlchemy(app)

@app.route('/')
def index():
    users = db.session.query(User).all()
    return render_template('users.html', users=users)

@app.route('/add', methods=['POST'])
def add_user():
    student_id = request.form.get('student_id')
    email = request.form.get('email')
    password_md5 = request.form.get('password')

    if not student_id or not email:
        flash('学号和邮箱是必填项。', 'danger')
        return redirect(url_for('index'))

    # If password field is empty, treat it as 'default'
    processed_password = password_md5 if password_md5 else 'default'

    new_user = User(student_id=student_id, email=email, password_md5=processed_password)
    db.session.add(new_user)
    db.session.commit()
    flash('用户添加成功。', 'success')
    return redirect(url_for('index'))

@app.route('/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    user = db.session.query(User).get_or_404(user_id)
    if request.method == 'POST':
        user.student_id = request.form.get('student_id')
        user.email = request.form.get('email')
        password_md5 = request.form.get('password')
        user.password_md5 = password_md5 if password_md5 else 'default'
        
        # Update reminder thresholds
        threshold1 = request.form.get('reminder_threshold_1')
        threshold2 = request.form.get('reminder_threshold_2')
        user.reminder_threshold_1 = int(threshold1) if threshold1 else 48
        user.reminder_threshold_2 = int(threshold2) if threshold2 else 24

        db.session.commit()
        flash('用户更新成功。', 'success')
        return redirect(url_for('index'))
    return render_template('edit_user.html', user=user)

@app.route('/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user = db.session.query(User).get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/user/<int:user_id>/homework')
def user_homework(user_id):
    user = db.session.query(User).get_or_404(user_id)
    return render_template('homework.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)
