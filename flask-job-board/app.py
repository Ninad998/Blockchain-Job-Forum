import os
import pymysql
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from passlib.hash import pbkdf2_sha256
from functools import wraps
# from flask_seasurf import SeaSurf
# from flask_gravatar import Gravatar

import settings

app = Flask(__name__)
app.config.from_object(settings)
# csrf = SeaSurf(app)
# gravatar = Gravatar(app, size=160, default='mm')

db = pymysql.connect(db="job_board", host="localhost", user="root", passwd="root", port=3306)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("logged_in"):
            return f(*args, **kwargs)
        else:
            flash(u'Login is required.', 'warning')
            return redirect(url_for('login', next=request.url))

    return decorated_function


@app.template_filter()
def timesince(dt, default="just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    """

    now = datetime.utcnow().date()
    diff = now - dt

    periods = (
        (diff.days / 365, "year", "years"), (diff.days / 30, "month", "months"), (diff.days / 7, "week", "weeks"),
        (diff.days, "day", "days"), (diff.seconds / 3600, "hour", "hours"), (diff.seconds / 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),)

    for period, singular, plural in periods:

        if period:
            return "%d %s ago" % (period, singular if period == 1 else plural)
    return default


@app.route("/")
def home():
    jobs = {}
    try:
        cur = db.cursor()
        query = "SELECT * FROM jobs;"
        cur.execute(query)
        response = cur.fetchall()
        jobs = []
        for item in response:
            job = dict()
            job['company_name'] = item[1]
            job['company_location'] = item[2]
            job['company_url'] = item[3]
            job['job_title'] = item[4]
            job['job_posting'] = item[5]
            job['application_instructions'] = item[6]
            job['created'] = item[7]
            jobs.append(job)
    except Exception as e:
        print(e)
    return render_template('home.html', jobs=jobs)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_job():
    if request.method == 'POST':
        joblist = []
        joblist.append(str(request.form['company_name']))
        joblist.append(str(request.form['company_location']))
        company_url = str(request.form['company_url'])
        if company_url[:4] == 'http':
            company_ur = company_url
        else:
            company_ur = 'http://' + company_url
        joblist.append(company_ur)
        joblist.append(str(request.form['job_title']))
        joblist.append(str(request.form['job_posting']))
        joblist.append(str(request.form['application_instructions']))
        joblist.append(datetime.utcnow().date().strftime('%m-%d-%y'))
        cur = db.cursor()
        try:
            query = "INSERT INTO jobs(company_name, company_location, company_url, job_title, job_posting, " \
                    "application_instructions, created) VALUES %r;" % (tuple(joblist))
            result = cur.execute(query)
            db.commit()
        except:
            query = "CREATE TABLE jobs(" \
                    "id int NOT NULL AUTO_INCREMENT," \
                    "company_name varchar(255)," \
                    "company_location varchar(255)," \
                    "company_url varchar(255)," \
                    "job_title varchar(255)," \
                    "job_posting varchar(255)," \
                    "application_instructions varchar(1000)," \
                    "created date, " \
                    "KEY(id), PRIMARY KEY(company_name));"
            cur.execute(query)
            query = "INSERT INTO jobs(company_name, company_location, company_url, job_title, job_posting, " \
                    "application_instructions, created) VALUES %r;" % (tuple(joblist))
            cur.execute(query)
            db.commit()

        cur = db.cursor()
        sql = "SELECT id FROM jobs ORDER BY id DESC LIMIT 1;"
        cur.execute(sql)
        response = cur.fetchone()
        job_id = 0
        for lastID in response:
            job_id = lastID
        next_url = job_id
        flash(u'Job successfully created.', 'success')
        return redirect(url_for('show_job', job_id=next_url))
    else:
        return render_template('create_job.html')


@app.route('/signup', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        if request.form['password'] == request.form['password2']:
            userlist = list()
            userlist.append(str(request.form['username']))
            userlist.append(str(request.form['email']))
            userlist.append(str(request.form['first_name']))
            userlist.append(str(request.form['last_name']))
            userlist.append('None')
            userlist.append('None')
            userlist.append(pbkdf2_sha256.hash(str(request.form['password'])))
            userlist.append(datetime.utcnow().date().strftime('%m-%d-%y'))

            session['username'] = str(request.form['username'])
            session['logged_in'] = True

            try:
                cur = db.cursor()
                query = "INSERT INTO users(username, email, first_name, last_name, location, homepage, " \
                        "passhash, created) VALUES %r;" % (tuple(userlist))
                result = cur.execute(query)
                db.commit()

            except:
                cur = db.cursor()
                query = "CREATE TABLE users(" \
                        "id int NOT NULL AUTO_INCREMENT, " \
                        "username varchar(50), " \
                        "email varchar(200), " \
                        "first_name varchar(50), " \
                        "last_name varchar(50), " \
                        "location varchar(200), " \
                        " homepage varchar(200), " \
                        "passhash varchar(500), " \
                        "created date, " \
                        "KEY(id),PRIMARY KEY(username));"
                cur.execute(query)
                uery = "INSERT INTO users(username, email, first_name, last_name, location, homepage, " \
                       "passhash, created) VALUES %r;" % (tuple(userlist))
                cur.execute(query)
                db.commit()

            cur = db.cursor()
            sql = "SELECT id FROM users ORDER BY id DESC LIMIT 1;"
            cur.execute(sql)
            response = cur.fetchone()
            for lastID in response:
                user_id = lastID

            flash(u'Successfully created new user.', 'success')
            return redirect(url_for('show_user', user_id=user_id))
        else:
            flash(u'Passwords do not match.', 'error')
            return render_template('create_user.html')
    else:
        return render_template('create_user.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    next = request.values.get('next', '')
    if request.method == 'POST':
        try:
            cur = db.cursor()
            query = "SELECT * FROM users WHERE username='%s';" % str(request.form['username'])
            result = cur.execute(query)
            response = cur.fetchone()
            username = response[1]
            password = response[7]
        except:
            flash(u'Password or Username is incorrect.', 'error')
            return render_template('login.html')
        else:
            if not pbkdf2_sha256.verify(request.form['password'], password):
                flash(u'Password or Username is incorrect.', 'error')
                return render_template('login.html')
            else:
                session['username'] = username
                session['logged_in'] = True
                flash(u'You have been successfully logged in.', 'success')
                return redirect(next or url_for('home'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('logged_in', None)
    flash(u'You have been successfully logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        cur = db.cursor()
        query = "SELECT id FROM users where username='%s';" % str(session.get('username'))
        cur.execute(query)
        response = cur.fetchone()
        user_id = 0
        for lastID in response:
            user_id = lastID

        cur = db.cursor()
        query = "UPDATE users SET email='%s', first_name='%s', last_name='%s', location='%s', " \
                "homepage='%s' WHERE id=%s;" % (
                    str(request.form['email']), str(request.form['first_name']),
                    str(request.form['last_name']), str(request.form['location']),
                    str(request.form['homepage']), user_id)
        result = cur.execute(query)
        db.commit()
        flash(u'Profile was successfully updated.', 'success')
        return redirect(url_for('show_user', user_id=user_id))
    else:
        cur = db.cursor()
        query = "SELECT * FROM users WHERE username='%s';" % str(session.get('username'))
        result = cur.execute(query)
        response = cur.fetchone()
        user = {'id': response[0], 'username': response[1], 'email': response[2], 'first_name': response[3],
                'last_name': response[4], 'location': response[5], 'homepage': response[6], 'created': response[8]}
        return render_template('settings.html', user=user)


@app.route('/user/<user_id>')
def show_user(user_id):
    cur = db.cursor()
    query = "SELECT * FROM users WHERE id=%s;" % str(user_id)
    result = cur.execute(query)
    response = cur.fetchone()
    user = {'id': response[0], 'username': response[1], 'email': response[2], 'first_name': response[3],
            'last_name': response[4], 'location': response[5], 'homepage': response[6], 'created': response[8]}
    return render_template('show_user.html', user=user)


@app.route('/job/<job_id>')
def show_job(job_id):
    cur = db.cursor()
    query = "SELECT * FROM jobs WHERE id=%s;" % str(job_id)
    result = cur.execute(query)
    response = cur.fetchone()
    job = {'id': response[0], 'company_name': response[1], 'company_location': response[2], 'company_url': response[3],
           'job_title': response[4], 'job_posting': response[5], 'application_instructions': response[6],
           'created': response[7]}
    return render_template('show_job.html', job=job)


@app.route('/users')
def show_all_users():
    cur = db.cursor()
    query = "SELECT * FROM users;"
    result = cur.execute(query)
    response = cur.fetchall()
    users = []
    for item in response:
        user = {}
        user['id'] = item[0]
        user['username'] = item[1]
        user['email'] = item[2]
        user['created'] = item[8]
        users.append(user)
    return render_template('show_all_users.html', users=users)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.debug = True
    app.run(host='0.0.0.0', port=port)
