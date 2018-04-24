import os
from datetime import datetime
import flask
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flaskext.mysql import MySQL
import flask_login
from werkzeug.utils import secure_filename
from passlib.hash import pbkdf2_sha256
from functools import wraps
import settings

UPLOAD_FOLDER = os.path.dirname(os.path.realpath(__file__)) + "/static/documents"
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg'}

app = Flask(__name__)
app.config.from_object(settings)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'root'
app.config['MYSQL_DATABASE_DB'] = 'job_board'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
mysql.init_app(app)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)


def getMysqlConnection():
    connection = mysql.connect()
    cursor = connection.cursor()
    return {"cursor": cursor, "conn": connection}


class User(flask_login.UserMixin):
    pass


def getUserList():
    db = getMysqlConnection()
    conn = db['conn']
    cursor = db['cursor']

    cursor.execute("SELECT username FROM users;")

    cursor.close()
    conn.close()
    return cursor.fetchall()


@login_manager.user_loader
def user_loader(email):
    users = getUserList()
    if not email or email not in str(users):
        return
    user = User()
    user.id = email
    return user


@app.template_filter()
def timesince(dt, default="just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    """
    f = '%Y-%m-%d %H:%M:%S'
    dt = datetime.strptime(str(dt), f)
    now = datetime.now()
    diff = now - dt

    periods = (
        (diff.days / 365, "year", "years"),
        (diff.days / 30, "month", "months"),
        (diff.days / 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds / 3600, "hour", "hours"),
        (diff.seconds / 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
        )

    for period, singular, plural in periods:
        if int(period) > 0:
            return "%d %s ago" % (period, singular if period == 1 else plural)

    return default


def loginuser(username):
    user = User()
    user.id = str(request.form['username'])
    flask_login.login_user(user)
    session['username'] = flask_login.current_user.id
    session['logged_in'] = True


def checkapplications(username):
    ret = False
    try:
        user = str(flask_login.current_user.id)
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM applications WHERE username LIKE '%%%s%%';" % user;
        cursor.execute(query)
        response = cursor.fetchall()
        if len(response) > 0:
            ret = True
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    return ret


def generatejob(response):
    if flask_login.current_user.is_authenticated:
        allow_apply = not flask_login.current_user.id == response[8]
        allow_apply = allow_apply and not checkapplications(flask_login.current_user.id)
    else:
        allow_apply = False

    job = {
        'id': response[0], 'company_name': response[1], 'company_location': response[2],
        'company_url': response[3], 'job_title': response[4], 'job_posting': response[5],
        'application_instructions': response[6], 'created': response[7], 'createdby': response[8],
        'allow_apply': allow_apply
    }

    return job


@app.route("/")
def home():
    jobs = list()
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM jobs;"
        cursor.execute(query)
        response = cursor.fetchall()
        cursor.close()
        conn.close()
        jobs = list()
        for item in response:
            job = generatejob(item)
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
@flask_login.login_required
def create_job():
    if request.method == 'POST':
        joblist = list()
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
        joblist.append(str(flask_login.current_user.id))
        try:
            db = getMysqlConnection()
            conn = db['conn']
            cursor = db['cursor']
            query = "INSERT INTO jobs(company_name, company_location, " \
                    "company_url, job_title, job_posting, application_instructions, " \
                    "createdby) VALUES %r;" % (tuple(joblist),)
            cursor.execute(query)
            conn.commit()
        except Exception as e:
            print(e)
        finally:
            cursor.close()
        conn.close()

        try:
            db = getMysqlConnection()
            conn = db['conn']
            cursor = db['cursor']
            query = "SELECT id FROM jobs ORDER BY id DESC LIMIT 1;"
            cursor.execute(query)
            response = cursor.fetchone()
        except Exception as e:
            print(e)
        finally:
            cursor.close()
            conn.close()

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
            userlist.append(str(request.form['first_name']))
            userlist.append(str(request.form['last_name']))
            userlist.append(pbkdf2_sha256.hash(str(request.form['password'])))
            loginuser(str(request.form['username']))

            try:
                db = getMysqlConnection()
                conn = db['conn']
                cursor = db['cursor']
                query = "INSERT INTO users(username, first_name, last_name, " \
                        "passhash) VALUES %r;" % (tuple(userlist),)
                cursor.execute(query)
                conn.commit()
            except Exception as e:
                print(e)
            finally:
                cursor.close()
                conn.close()

            try:
                db = getMysqlConnection()
                conn = db['conn']
                cursor = db['cursor']
                query = "SELECT id FROM users ORDER BY id DESC LIMIT 1;"
                cursor.execute(query)
                response = cursor.fetchone()
            except Exception as e:
                print(e)
            finally:
                cursor.close()
                conn.close()

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
            db = getMysqlConnection()
            conn = db['conn']
            cursor = db['cursor']
            query = "SELECT username, passhash FROM users WHERE username='%s';" % str(request.form['username'])
            result = cursor.execute(query)
            response = cursor.fetchone()
            username = response[0]
            password = response[1]

        except Exception as e:
            print(e)
            flash(u'Password or Username is incorrect.', 'error')
            return render_template('login.html')
        finally:
            cursor.close()
            conn.close()

        if not pbkdf2_sha256.verify(request.form['password'], password):
            flash(u'Password or Username is incorrect.', 'error')
            return render_template('login.html')
        else:
            loginuser(username)
            flash(u'You have been successfully logged in.', 'success')
            return redirect(next or url_for('home'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    flask_login.logout_user()
    session.pop('username')
    session.pop('logged_in')
    flash(u'You have been successfully logged out.', 'info')
    return redirect(url_for('home'))


def getuser(response):
    user = {
        'id': response[0], 'username': response[1], 'first_name': response[2],
        'last_name': response[3], 'created': response[5]
    }
    return user


@app.route('/settings', methods=['GET', 'POST'])
@flask_login.login_required
def settings():
    if request.method == 'POST':
        try:
            db = getMysqlConnection()
            conn = db['conn']
            cursor = db['cursor']
            query = "SELECT id FROM users where username='%s';" % str(flask_login.current_user.id)
            cursor.execute(query)
            response = cursor.fetchone()
        except Exception as e:
            print(e)
        finally:
            cursor.close()
            conn.close()

        user_id = 0
        for lastID in response:
            user_id = lastID

        try:
            db = getMysqlConnection()
            conn = db['conn']
            cursor = db['cursor']
            query = "UPDATE users SET email='%s', first_name='%s', last_name='%s', location='%s', " \
                    "homepage='%s' WHERE id=%s;" % (
                        str(request.form['email']), str(request.form['first_name']),
                        str(request.form['last_name']), str(request.form['location']),
                        str(request.form['homepage']), user_id)
            result = cursor.execute(query)
            conn.commit()
        except Exception as e:
            print(e)
        finally:
            cursor.close()
            conn.close()

        flash(u'Profile was successfully updated.', 'success')
        return redirect(url_for('show_user', user_id=user_id))
    else:
        try:
            db = getMysqlConnection()
            conn = db['conn']
            cursor = db['cursor']
            query = "SELECT * FROM users WHERE username='%s';" % str(flask_login.current_user.id)
            result = cursor.execute(query)
            response = cursor.fetchone()
        except Exception as e:
            print(e)
        finally:
            cursor.close()
            conn.close()

        user = getuser(response)
        return render_template('settings.html', user=user)


@app.route('/user/<user_id>')
def show_user(user_id):
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM users WHERE id=%s;" % str(user_id)
        result = cursor.execute(query)
        response = cursor.fetchone()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    user = getuser(response)
    return render_template('show_user.html', user=user)


@app.route('/job/<job_id>')
def show_job(job_id):
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM jobs WHERE id=%s;" % str(job_id)
        result = cursor.execute(query)
        response = cursor.fetchone()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    job = generatejob(response)

    return render_template('show_job.html', job=job)


# return list of allowed files
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


def saveCV(job_id, username, dir, desc):
    id = 0
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO applications " \
                "(jobid, username, dir, description) " \
                "VALUES (\"%s\", \"%s\", \"%s\", \"%s\");" % (job_id, username, dir, desc)
        result = cursor.execute(query)

        cursor.execute("SELECT id FROM applications WHERE dir LIKE '%%%s%%' ORDER BY dateofcreation LIMIT 1;" % dir)

        id = cursor.fetchone()[0]
        conn.commit()

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    return id


@app.route('/apply/<job_id>', methods=['GET', 'POST'])
@flask_login.login_required
def apply(job_id):
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM jobs WHERE id=%s;" % str(job_id)
        result = cursor.execute(query)
        response = cursor.fetchone()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    job = generatejob(response)

    if request.method == 'GET':
        return render_template('apply.html', job = job)

    try:
        file = request.files['cv']
        desc = request.form.get('desc')
    except:
        print("couldn't find all tokens")
        flash(u'Re-upload please', 'error')
        return render_template('apply.html', job = job)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        directory = app.config['UPLOAD_FOLDER']
        name = "/" + str(job_id)

        if not os.path.exists(directory + name):
            os.makedirs(directory + name)

        listOfFiles = [f for f in os.listdir(directory + name)]
        i = 1
        for f in listOfFiles:
            currentfile = f.split(".")[-2]
            if i > int(currentfile):
                pass
            else:
                i = int(currentfile) + 1

        file.save(os.path.join(directory + name, filename))
        source = directory + name + "/" + filename
        extension = str(filename.split(".")[1])

        newname = directory + name + "/" + str(i) + "." + extension
        os.rename(source, newname)

        dir = name + "/" + str(i) + "." + extension

        saveCV(job_id, flask_login.current_user.id, dir, desc)

    return flask.redirect(flask.url_for('home'))


@app.route('/users')
def show_all_users():
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM users;"
        result = cursor.execute(query)
        response = cursor.fetchall()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    users = list()
    for item in response:
        user = dict()
        user['id'] = item[0]
        user['username'] = item[1]
        user['email'] = item[2]
        user['created'] = item[8]
        users.append(user)
    return render_template('show_all_users.html', users=users)


@app.route('/applied')
@flask_login.login_required
def applied():
    jobs = list()
    try:
        user = str(flask_login.current_user.id)
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT DISTINCT jobid FROM applications WHERE username LIKE '%%%s%%';" % user;
        cursor.execute(query)
        response = cursor.fetchall()
        jobs = list()
        for item in response:
            query = "SELECT * FROM jobs WHERE id=%s;" % str(item[0])
            result = cursor.execute(query)
            response = cursor.fetchone()
            job = generatejob(response)
            jobs.append(job)

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return render_template('applied.html', jobs = jobs)


@app.route('/company')
@flask_login.login_required
def list_jobs():
    jobs = list()
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM jobs WHERE createdby LIKE '%%%s%%';" % str(flask_login.current_user.id)
        cursor.execute(query)
        response = cursor.fetchall()
        jobs = list()
        for item in response:
            job = generatejob(item)
            jobs.append(job)
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return render_template('company.html', jobs = jobs)


@app.route('/list_applications/<job_id>')
@flask_login.login_required
def list_applications(job_id):
    jobs = list()
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM applications WHERE jobid = %s;" % str(job_id)
        cursor.execute(query)
        response = cursor.fetchall()
        jobs = list()
        for item in response:
            job = dict()
            job['id'] = item[0]
            job['jobid'] = item[1]
            job['username'] = item[2]
            job['dir'] = item[3]
            job['cvname'] = item[3].split("/")[1] + "_" + item[3][3].split(".")[0]
            job['desc'] = item[4]
            job['dateofcreation'] = item[5]
            query = "SELECT * FROM users WHERE username='%s';" % str(item[2])
            result = cursor.execute(query)
            response = cursor.fetchone()
            job['user'] = getuser(response)
            print(job)
            jobs.append(job)
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return render_template('list_applications.html', jobs = jobs)


@app.route('/view/<cvname>')
@flask_login.login_required
def viewpdf(cvname):
    path = "documents/" + cvname.split("_")[0] + "/" + cvname.split("_")[1] + ".pdf"
    cvpath = url_for("static", filename = path)
    print(cvpath)
    return render_template('view_pdf.html', cvpath = cvpath)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


def check_db():
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM users LIMIT 1;"
        cursor.execute(query)
    except Exception as e:
        print(e)
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "CREATE TABLE users(" \
                "id int NOT NULL AUTO_INCREMENT, " \
                "username varchar(50), " \
                "first_name varchar(50), " \
                "last_name varchar(50), " \
                "passhash varchar(500), " \
                "created DATETIME DEFAULT CURRENT_TIMESTAMP, " \
                "KEY(id),PRIMARY KEY(username));"
        cursor.execute(query)
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM jobs LIMIT 1;"
        cursor.execute(query)
    except Exception as e:
        print(e)
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "CREATE TABLE jobs(" \
                "id int NOT NULL AUTO_INCREMENT," \
                "company_name varchar(255)," \
                "company_location varchar(255)," \
                "company_url varchar(255)," \
                "job_title varchar(255)," \
                "job_posting varchar(255)," \
                "application_instructions varchar(1000)," \
                "created DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, " \
                "createdby varchar(50), " \
                "CONSTRAINT fk_key_1 FOREIGN KEY (createdby) " \
                "REFERENCES users (username) ON DELETE CASCADE ON UPDATE CASCADE, " \
                "KEY(id), PRIMARY KEY(company_name));"
        cursor.execute(query)
        conn.commit()
    finally:
        cursor.close()
        conn.close()

        try:
            db = getMysqlConnection()
            conn = db['conn']
            cursor = db['cursor']
            query = "SELECT * FROM applications LIMIT 1;"
            cursor.execute(query)
        except Exception as e:
            print(e)
            db = getMysqlConnection()
            conn = db['conn']
            cursor = db['cursor']
            query = "CREATE TABLE applications(" \
                    "id int NOT NULL AUTO_INCREMENT," \
                    "jobid int(11) NOT NULL," \
                    "username varchar(45) NOT NULL," \
                    "dir varchar(45) DEFAULT NULL," \
                    "description varchar(255)," \
                    "dateofcreation DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP," \
                    "CONSTRAINT fk_key_2 FOREIGN KEY (jobid) " \
                    "REFERENCES jobs (id) ON DELETE CASCADE ON UPDATE CASCADE, " \
                    "CONSTRAINT fk_key_3 FOREIGN KEY (username) " \
                    "REFERENCES users (username) ON DELETE CASCADE ON UPDATE CASCADE, " \
                    "KEY(id), PRIMARY KEY (jobid, username));"
            cursor.execute(query)
            conn.commit()
        finally:
            cursor.close()
            conn.close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    check_db()
    app.debug = True
    app.run(host='0.0.0.0', port=port)
