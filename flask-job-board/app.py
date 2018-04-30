"""
Team: 
Ninad Tungare        U49815021
Harshad Nalla Reddy  U60360285
Chunar Singh         U10488522

"""
# Packages
import flask
import requests
import settings
import flask_login
import pandas as pd
from uuid import uuid4
from copy import deepcopy
from datetime import datetime
from flaskext.mysql import MySQL
from blockchain import BlockChain
from argparse import ArgumentParser
from passlib.hash import pbkdf2_sha256
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify

app = Flask(__name__)
app.config.from_object(settings)

mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'root'
app.config['MYSQL_DATABASE_DB'] = 'job_board'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['BLOCKCHAIN_LENGTH'] = 10
mysql.init_app(app)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)

# Blockchain object
blockchain = BlockChain()
# Unique address for current node
node_address = uuid4().hex


def getMysqlConnection():
    connection = mysql.connect()
    cursor = connection.cursor()
    return {"cursor": cursor, "conn": connection}


class User(flask_login.UserMixin):
    pass


db = getMysqlConnection()
conn = db['conn']
cursor = db['cursor']
cursor.close()
conn.close()


def getUserList():
    global cursor, conn
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
def timesince(dt, default = "just now"):
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


def login_user(username, account_type):
    user = User()
    user.id = username
    flask_login.login_user(user)
    session['username'] = flask_login.current_user.id
    session['logged_in'] = True
    session['account_type'] = account_type


def check_applications(job_id, username):
    ret = False
    jobs = get_application_details_blockchain(job_id = job_id, username = username)
    if isinstance(jobs,dict) and len(jobs) > 0:
        ret = True
    # try:
    #     user = str(flask_login.current_user.id)
    #     db = getMysqlConnection()
    #     conn = db['conn']
    #     cursor = db['cursor']
    #     query = "SELECT * FROM applications WHERE username LIKE '%%%s%%' and job_id = '%s';" % user,job_id
    #     cursor.execute(query)
    #     response = cursor.fetchall()
    #     if len(response) > 0:
    #         ret = True
    # except Exception as e:
    #     print(e)
    # finally:
    #     cursor.close()
    #     conn.close()
    return ret


def get_user_details_blockchain(user_id = '', username = ''):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e)
    chain = blockchain.get_serialized_chain
    # if len(chain) > app.config['BLOCKCHAIN_LENGTH']:
    #     for i,each_block in enumerate(chain):
    #         if each_block.get('body', []) and each_block['body'][0].get('user'):
    #             user = deeepcopy(each_block['body'][0].get('user'))
    #             insert_user_db([user['id'],user['username'], user['first_name'], user['last_name'], user['passhash'], user['account_type'], user['created']])
    #             blockchain.remove_block_in_chain(each_block['index'])
    # elif 
    count = 0
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('user'):
                count += 1
                if user_id:
                    if each_block['body'][0]['user']['id'] == int(user_id):
                        return deepcopy(each_block['body'][0].get('user'))
                elif username:
                    print("data", each_block['body'][0]['user'])
                    if each_block['body'][0]['user']['username'] == username:
                        return deepcopy(each_block['body'][0].get('user'))
    return count


def get_user_details_db(user_id = '', username = ''):
    global cursor, conn
    user = dict()
    count = 0
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if user_id:
            query = "SELECT * FROM users WHERE id = %s;" % user_id
        elif username:
            query = "SELECT * FROM users WHERE username = %s;" % username
        else:
            query = "SELECT * FROM users;"
        cursor.execute(query)
        response = cursor.fetchall()
        if len(response) > 1:
            count = len(response)
        else:
            response = cursor.fetchone()
            user = {
                'id': response[0],
                'username': response[1],
                'first_name': response[2],
                'last_name': response[3],
                'password': response[4],
                'account_type': response[5],
                'created': response[6],
                }

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    if count > 0:
        return count

    return user


def insert_user_db(user):
    global cursor, conn
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO users " \
                "(id, username, first_name, last_name, passhash, account_type, created) " \
                "VALUES %r;" % (tuple(user),)
        cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return True


def update_user_db(user):
    global cursor, conn
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "UPDATE users SET " \
                "username='%s', first_name='%s', last_name='%s', passhash='%s', " \
                "account_type='%s', created='%s' " \
                "WHERE id=%s;" % (user['username'], user['first_name'],
                                  user['last_name'], user['password'],
                                  user['account_type'], user['created'],
                                  user['id'])
        cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()


def get_job_details_blockchain(job_id = ''):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e) 
    chain = blockchain.get_serialized_chain
    count = 0
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('job'):
                count += 1
                if job_id:
                    if each_block['body'][0]['job']['id'] == int(job_id):
                        return deepcopy(each_block['body'][0].get('job'))
    return count


def get_job_details_db(job_id = ''):
    global cursor, conn
    job = dict()
    count = 0
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if job_id:
            query = "SELECT * FROM jobs WHERE id = %s;" % job_id
        else:
            query = "SELECT * FROM jobs;"

        cursor.execute(query)
        response = cursor.fetchall()
        if len(response) > 1:
            count = len(response)
        else:
            response = cursor.fetchone()
            job = {
                'id': response[0],
                'company_name': response[1],
                'company_location': response[2],
                'company_url': response[3],
                'job_title': response[4],
                'job_posting': response[5],
                'application_instructions': response[6],
                'created': response[7],
                'createdby': response[8],
                'status': response[9],
                'username': response[10],
                }

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    if count > 0:
        return count

    return job


def get_job_list(username = ''):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e)
    chain = blockchain.get_serialized_chain
    blockchain_job_list = []
    job_set=set()
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('job'):
                if each_block['body'][0]['job']['id'] not in job_set:
                    job_set.add(each_block['body'][0]['job']['id'])
                    if username:
                        if each_block['body'][0]['job']['createdby'] == username:
                            blockchain_job_list.append(each_block['body'][0].get('job'))
                    else:
                        blockchain_job_list.append(each_block['body'][0].get('job'))
    return blockchain_job_list


def get_job_list_db(username = ''):
    global cursor, conn
    jobs = list()
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if username:
            query = "SELECT * FROM jobs WHERE createdby LIKE %%%s%%;" % username
        else:
            query = "SELECT * FROM jobs;"
        cursor.execute(query)
        response = cursor.fetchall()
        for row in response:
            job = {
                'id': row[0],
                'company_name': row[1],
                'company_location': row[2],
                'company_url': row[3],
                'job_title': row[4],
                'job_posting': row[5],
                'application_instructions': row[6],
                'created': row[7],
                'createdby': row[8],
                'status': row[9],
                'username': row[10],
                }
            jobs.append(job)

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    return jobs


def insert_job_db(job):
    global cursor, conn
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO jobs " \
                "(id, company_name, company_location, company_url, job_title, " \
                "job_posting, application_instructions, created, createdby, " \
                "status, username) VALUES %r;" % tuple(job)
        cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()


def update_job_db(job):
    global cursor, conn
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "UPDATE jobs SET " \
                "company_name='%s', company_location='%s', company_url='%s', job_title='%s', " \
                "job_posting='%s', application_instructions='%s', created='%s', createdby='%s', " \
                "status='%s', username='%s' " \
                "WHERE id=%s;" % (job['company_name'], job['company_location'], job['company_url'],
                                  job['job_title'], job['job_posting'], job['application_instructions'],
                                  job['created'], job['createdby'], job['status'], job['username'],
                                  job['id'])
        cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()


def get_application_details_blockchain(job_id = '', username = '', app_id = ''):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e)
    chain = blockchain.get_serialized_chain
    blockchain_application_list = []
    count = 0
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('application'):
                count +=1
                if app_id:
                    if int(each_block['body'][0]['application']['id']) == int(app_id):
                        return deepcopy(each_block['body'][0].get('application'))
                elif job_id and username:
                    if int(each_block['body'][0]['application']['job_id']) == int(job_id) and \
                            each_block['body'][0]['application']['username'] == username:
                        return deepcopy(each_block['body'][0].get('application'))
    return count


def get_application_details_db(job_id = '', username = '', app_id = ''):
    global cursor, conn
    application = dict()
    count = 0
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if app_id:
            query = "SELECT * FROM applications WHERE id = %s;" % app_id
        elif job_id and username:
            query = "SELECT * FROM applications WHERE job_id = %s AND username LIKE %%%s%%;" % (job_id, username)
        else:
            query = "SELECT * FROM applications;"
        cursor.execute(query)
        response = cursor.fetchall()
        if len(response) > 1:
            count = len(response)
        else:
            response = cursor.fetchone()
            application = {
                'id': response[0],
                'job_id': response[1],
                'username': response[2],
                'description': response[3],
                'dateofcreation': response[4],
                }

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    if count > 0:
        return count

    return application


def get_application_list(job_id = '', username = ''):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e)
    chain = blockchain.get_serialized_chain
    blockchain_application_list = []
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('application'):
                if job_id:
                    if int(each_block['body'][0]['application']['job_id']) == int(job_id):
                        blockchain_application_list.append(each_block['body'][0].get('application'))
                elif username:
                    if each_block['body'][0]['application']['username'] == username:
                        blockchain_application_list.append(each_block['body'][0].get('application'))
                else:
                    blockchain_application_list.append(each_block['body'][0].get('application'))
    return blockchain_application_list


def get_application_list_db(job_id = '', username = ''):
    global cursor, conn
    applications = list()
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if job_id:
            query = "SELECT * FROM applications WHERE id = %s;" % job_id
        elif username:
            query = "SELECT * FROM applications WHERE username LIKE %%%s%%;" % username
        else:
            query = "SELECT * FROM applications;"
        cursor.execute(query)
        response = cursor.fetchall()
        for row in response:
            application = {
                'id': response[0],
                'job_id': response[1],
                'username': response[2],
                'description': response[3],
                'dateofcreation': response[4],
                }
            applications.append(application)

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    return applications


def insert_application_db(application):
    global cursor, conn
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO applications " \
                "(id, job_id, username, description, dateofcreation) " \
                "VALUES %r;" % tuple(application)
        cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()


def update_application_db(application):
    global cursor, conn
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "UPDATE applications SET " \
                "job_id='%s', username='%s', description='%s', dateofcreation='%s' " \
                "WHERE id=%s;" % (application['job_id'], application['username'],
                                  application['description'], application['dateofcreation'],
                                  application['id'])
        cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()


def generatejob(response):
    if flask_login.current_user.is_authenticated:
        allow_apply = not flask_login.current_user.id == response[8]
        # allow_apply = allow_apply and not check_applications(
        #     flask_login.current_user.id)
    else:
        allow_apply = False

    job = {
        'id': response[0], 'company_name': response[1], 'company_location': response[2],
        'company_url': response[3], 'job_title': response[4], 'job_posting': response[5],
        'application_instructions': response[6], 'created': response[7], 'createdby': response[8],
        'allow_apply': allow_apply
        }

    return job


def getuser(response):
    user = {
        'id': response[0],
        'username': response[1],
        'first_name': response[2],
        'last_name': response[3],
        'created': response[5]
        }
    return user


@app.route("/")
def home():
    jobs = get_job_list()
    print("jobs home", jobs)
    # else:
    #     try:
    #         db = getMysqlConnection()
    #         conn = db['conn']
    #         cursor = db['cursor']
    #         query = "SELECT * FROM jobs;"
    #         cursor.execute(query)
    #         response = cursor.fetchall()
    #         cursor.close()
    #         conn.close()
    #         jobs = list()
    #         for item in response:
    #             job = generatejob(item)
    #             jobs.append(job)
    #     except Exception as e:
    #         print(e)
    return render_template('home.html', jobs = jobs)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/create', methods = ['GET', 'POST'])
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

        # Block chain initailization
        transaction_data = {}
        job_form_data = {
            'company_name': str(request.form['company_name']),
            'company_location': str(request.form['company_location']),
            'company_url': company_ur,
            'job_title': str(request.form['job_title']),
            'job_posting': str(request.form['job_posting']),
            'application_instructions': str(request.form['application_instructions']),
            'createdby': flask_login.current_user.id,
            'created': str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            'id': get_job_details_blockchain()+1,
            'status':'not_selected',
            'payment': str(request.form['payment'])
            }
        print("job_form_data", job_form_data)
        transaction_data['job'] = job_form_data
        index = blockchain.create_new_transaction(transaction_data)
        if index:
            result = mine(uuid4().hex)
        if result.get('status', False):
            # try:
            #     db = getMysqlConnection()
            #     conn = db['conn']
            #     cursor = db['cursor']
            #     query = "INSERT INTO jobs(company_name, company_location, " \
            #             "company_url, job_title, job_posting, application_instructions, " \
            #             "createdby) VALUES %r;" % (tuple(joblist),)
            #     cursor.execute(query)
            #     conn.commit()
            # except Exception as e:
            #     print(e)
            # finally:
            #     cursor.close()
            # conn.close()

            # try:
            #     db = getMysqlConnection()
            #     conn = db['conn']
            #     cursor = db['cursor']
            #     query = "SELECT id FROM jobs ORDER BY id DESC LIMIT 1;"
            #     cursor.execute(query)
            #     response = cursor.fetchone()
            # except Exception as e:
            #     print(e)
            # finally:
            #     cursor.close()
            #     conn.close()

            # job_id = 0
            # for lastID in response:
            #     job_id = lastID
            # according to blockchain
            next_url = get_job_details_blockchain()
            flash(u'Job successfully created.', 'success')
            return redirect(url_for('show_job', job_id = next_url))

        else:
            flash(u'Mining of the block dint complete successfully.', 'error')
            return render_template('create_job.html')
    else:
        return render_template('create_job.html')


@app.route('/signup', methods = ['GET', 'POST'])
def signup():
    if request.method == 'POST':
        if request.form['password'] == request.form['password2']:
            userlist = list()
            userlist.append(str(request.form['username']))
            userlist.append(str(request.form['first_name']))
            userlist.append(str(request.form['last_name']))
            userlist.append(pbkdf2_sha256.hash(str(request.form['password'])))
            userlist.append(str(request.form['account_type']))
            login_user(str(request.form['username']), str(request.form['account_type']))

            # Block chain initailization
            transaction_data = {}
            user_form_data = {
                'id': get_user_details_blockchain()+1,
                'username': str(request.form['username']),
                'first_name': str(request.form['first_name']),
                'last_name': str(request.form['last_name']),
                'password': pbkdf2_sha256.hash(str(request.form['password'])),
                'account_type': str(request.form['account_type']),
                'created': str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                }
            transaction_data['user'] = user_form_data
            index = blockchain.create_new_transaction(transaction_data)
            if index:
                result = mine(uuid4().hex)

            if result.get('status', False):
                # try:
                #     db = getMysqlConnection()
                #     conn = db['conn']
                #     cursor = db['cursor']
                #     query = "INSERT INTO users " \
                #             "(username, first_name, last_name, passhash, account_type)" \
                #             "VALUES %r;" % (tuple(userlist),)
                #     cursor.execute(query)
                #     conn.commit()
                # except Exception as e:
                #     print(e)
                # finally:
                #     cursor.close()
                #     conn.close()

                # try:
                #     db = getMysqlConnection()
                #     conn = db['conn']
                #     cursor = db['cursor']
                #     query = "SELECT id FROM users ORDER BY id DESC LIMIT 1;"
                #     cursor.execute(query)
                #     response = cursor.fetchone()
                # except Exception as e:
                #     print(e)
                # finally:
                #     cursor.close()
                #     conn.close()

                # for lastID in response:
                #     user_id = lastID

                # according to blockchian:
                user_id = get_user_details_blockchain()
                flash(u'Successfully created new user.', 'success')
                return redirect(url_for('home'))
            else:
                flash(u'Mining of the block dint complete successfully.', 'error')
                return render_template('create_user.html')
        else:
            flash(u'Passwords do not match.', 'error')
            return render_template('create_user.html')
    else:
        return render_template('create_user.html')


@app.route('/login', methods = ['GET', 'POST'])
def login():
    next = request.values.get('next', '')
    if request.method == 'POST':
        user_flag = False
        try:
            user_details = get_user_details_blockchain(username=str(request.form['username']))
            if isinstance(user_details, int):
                flash(u'User doesnt exist.', 'error')
                return render_template('login.html')
            else:
                username = user_details['username']
                password = user_details['password']
                account_type = user_details['account_type']
                user_flag = True

        except Exception as e:
            print(e)
            flash(u'Password or Username is incorrect.', 'error')
            return render_template('login.html')

        # try:
        #     db = getMysqlConnection()
        #     conn = db['conn']
        #     cursor = db['cursor']
        #     query = "SELECT username, passhash, account_type" \
        #             "FROM users " \
        #             "WHERE username='%s';" % str(request.form['username'])
        #     result = cursor.execute(query)
        #     response = cursor.fetchone()
        #     username = response[0]
        #     password = response[1]
        #     account_type = response[2]

        # except Exception as e:
        #     print(e)
        #     flash(u'Password or Username is incorrect.', 'error')
        #     return render_template('login.html')
        # finally:
        #     cursor.close()
        #     conn.close()
        if user_flag:
            if not pbkdf2_sha256.verify(request.form['password'], password):
                flash(u'Password or Username is incorrect.', 'error')
                return render_template('login.html')
            else:
                login_user(username, account_type)
                flash(u'You have been successfully logged in.', 'success')
                return redirect(next or url_for('home'))
        else:
            flash(u'User doesnt exist.', 'error')
            return render_template('login.html')
    return render_template('login.html')


@app.route('/logout')
def logout():
    flask_login.logout_user()
    if 'username' in session:
        session.pop('username')
    if 'logged_in' in session:
        session.pop('logged_in')
    if 'account_type' in session:
        session.pop('account_type')
    flash(u'You have been successfully logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/settings', methods = ['GET', 'POST'])
@flask_login.login_required
def settings():
    if request.method == 'POST':
        try:
            db = getMysqlConnection()
            conn = db['conn']
            cursor = db['cursor']
            query = "SELECT id FROM users where username='%s';" % str(
                flask_login.current_user.id)
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
            query = "UPDATE users SET " \
                    "username='%s', first_name='%s', last_name='%s', " \
                    "WHERE id=%s;" % (
                        str(request.form['username']),
                        str(request.form['first_name']),
                        str(request.form['last_name']), user_id)
            result = cursor.execute(query)
            conn.commit()
        except Exception as e:
            print(e)
        finally:
            cursor.close()
            conn.close()

        flash(u'Profile was successfully updated.', 'success')
        return redirect(url_for('show_user', user_id = user_id))
    else:
        try:
            db = getMysqlConnection()
            conn = db['conn']
            cursor = db['cursor']
            query = "SELECT * FROM users WHERE username='%s';" % str(
                flask_login.current_user.id)
            result = cursor.execute(query)
            response = cursor.fetchone()
        except Exception as e:
            print(e)
        finally:
            cursor.close()
            conn.close()

        user = getuser(response)
        return render_template('settings.html', user = user)


@app.route('/user/<user_id>')
def show_user(user_id):
    user = get_user_details_blockchain(str(user_id))
    # try:
    #     db = getMysqlConnection()
    #     conn = db['conn']
    #     cursor = db['cursor']
    #     query = "SELECT * FROM users WHERE id=%s;" % str(user_id)
    #     result = cursor.execute(query)
    #     response = cursor.fetchone()
    # except Exception as e:
    #     print(e)
    # finally:
    #     cursor.close()
    #     conn.close()
    # user = getuser(response)

    return render_template('show_user.html', user = user)


def check_applied(username):
    # TODO
    return False


def check_selected(username):
    # TODO
    return False

def get_transaction_details(job_id=""):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e) 
    chain = blockchain.get_serialized_chain
    count = 0
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('transaction'):
                count += 1
                if job_id:
                    if each_block['body'][0]['transaction']['job_id'] == int(job_id):
                        return deepcopy(each_block['body'][0].get('transaction'))
    return count

@app.route('/job/<job_id>')
def show_job(job_id):
    job = get_job_details_blockchain(str(job_id))
    applied = False
    payment = False
    if job:
        if flask_login.current_user.is_authenticated:
            allow_apply = not flask_login.current_user.id == job['createdby']
            allow_apply = allow_apply and not check_applications(job_id, flask_login.current_user.id)
            allow_apply = allow_apply and job['status'] == "not_selected"  
        else:
            allow_apply = False

        job['allow_apply'] = allow_apply

        if check_applications(job_id,session.get('username')):
            applied = True

        if job['status'] == "completed":
            amt = get_transaction_details(str(job_id))
            if amt:
                payment = True
    # try:
    #     db = getMysqlConnection()
    #     conn = db['conn']
    #     cursor = db['cursor']
    #     query = "SELECT * FROM jobs WHERE id=%s;" % str(job_id)
    #     result = cursor.execute(query)
    #     response = cursor.fetchone()
    # except Exception as e:
    #     print(e)
    # finally:
    #     cursor.close()
    #     conn.close()
    # job = generatejob(response)
    return render_template('show_job.html', job = job, applied = applied, payment =payment)


@app.route('/apply/<job_id>', methods = ['GET', 'POST'])
@flask_login.login_required
def apply(job_id):
    job = get_job_details_blockchain(str(job_id))

    if job:
        if flask_login.current_user.is_authenticated:
            allow_apply = not flask_login.current_user.id == job['createdby']
            allow_apply = allow_apply and not check_applications(job_id, flask_login.current_user.id)
        else:
            allow_apply = False

        job['allow_apply'] = allow_apply

    # try:
    #     db = getMysqlConnection()
    #     conn = db['conn']
    #     cursor = db['cursor']
    #     query = "SELECT * FROM jobs WHERE id=%s;" % str(job_id)
    #     result = cursor.execute(query)
    #     response = cursor.fetchone()
    # except Exception as e:
    #     print(e)
    # finally:
    #     cursor.close()
    #     conn.close()

    # job = generatejob(response)

    if request.method == 'GET':
        return render_template('apply.html', job = job)

    # Block chain initailization
    transaction_data = {}
    application_form_data = {
        'id': get_application_details_blockchain()+1,
        'job_id': str(job_id),
        'username': str(session['username']),
        'description': str(request.form.get('desc')),
        'dateofcreation': str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        }
    transaction_data['application'] = application_form_data
    index = blockchain.create_new_transaction(transaction_data)
    if index:
        result = mine(uuid4().hex)

    if result.get('status', False):
        print("Information is Mined")
        # try:
        #     db = getMysqlConnection()
        #     username = session['username']
        #     desc = request.form.get('desc')
        #     conn = db['conn']
        #     cursor = db['cursor']
        #     query = "INSERT INTO applications " \
        #             "(jobid, username, description) " \
        #             "VALUES (\"%s\", \"%s\", \"%s\");" % (job_id, username, desc)

        #     result = cursor.execute(query)
        #     conn.commit()

        # except Exception as e:
        #     print(e)
        # finally:
        #     cursor.close()
        #     conn.close()
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
    return render_template('show_all_users.html', users = users)


@app.route('/jobs_applied')
@flask_login.login_required
def jobs_applied():
    application = get_application_list(username = str(flask_login.current_user.id))
    jobs = []
    for each_application in application:
        job = get_job_details_blockchain(job_id = str(each_application['job_id']))
        jobs.append(job)
    # try:
    #     user = str(flask_login.current_user.id)
    #     db = getMysqlConnection()
    #     conn = db['conn']
    #     cursor = db['cursor']
    #     query = "SELECT DISTINCT jobid FROM applications WHERE username LIKE '%%%s%%';" % user
    #     cursor.execute(query)
    #     response = cursor.fetchall()
    #     jobs = list()
    #     for item in response:
    #         query = "SELECT * FROM jobs WHERE id=%s;" % str(item[0])
    #         result = cursor.execute(query)
    #         response = cursor.fetchone()
    #         job = generatejob(response)
    #         jobs.append(job)

    # except Exception as e:
    #     print(e)
    # finally:
    #     cursor.close()
    #     conn.close()
    return render_template('list_applications_by_user.html', jobs = jobs)


@app.route('/company')
@flask_login.login_required
def list_jobs():
    jobs = get_job_list(username = str(flask_login.current_user.id))
    print("list jobs", jobs)
    # try:
    #     db = getMysqlConnection()
    #     conn = db['conn']
    #     cursor = db['cursor']
    #     query = "SELECT * FROM jobs WHERE createdby LIKE '%%%s%%';" % str(
    #         flask_login.current_user.id)
    #     cursor.execute(query)
    #     response = cursor.fetchall()
    #     jobs = list()
    #     for item in response:
    #         job = generatejob(item)
    #         jobs.append(job)
    # except Exception as e:
    #     print(e)
    # finally:
    #     cursor.close()
    #     conn.close()
    return render_template('company.html', jobs = jobs)


@app.route('/list_applications/<job_id>')
@flask_login.login_required
def list_applications(job_id):
    application = get_application_list(job_id = str(job_id))
    jobs = []
    job_details = get_job_details_blockchain(job_id)
    for each_application in application:
        job = deepcopy(each_application)
        if job_details['status'] == 'not_selected':
            job['select_possible'] = True
        else:
            job['select_possible'] = False
        job['user']= get_user_details_blockchain(username=str(job['username']))
        if not job['select_possible']:
            if job_details['username']==job['username']:
                job['user']['selected']= True
            else:
                job['user']['selected'] = False
        jobs.append(job)
    # jobs = list()
    # try:
    #     db = getMysqlConnection()
    #     conn = db['conn']
    #     cursor = db['cursor']
    #     query = "SELECT * FROM applications WHERE jobid = %s;" % str(job_id)
    #     cursor.execute(query)
    #     response = cursor.fetchall()
    #     jobs = list()
    #     for item in response:
    #         job = dict()
    #         job['id'] = item[0]
    #         job['jobid'] = item[1]
    #         job['username'] = item[2]
    #         job['desc'] = item[3]
    #         job['dateofcreation'] = item[4]
    #         query = "SELECT * FROM users WHERE username='%s';" % str(item[2])
    #         result = cursor.execute(query)
    #         response = cursor.fetchone()
    #         job['user'] = getuser(response)
    #         job['user']['selected'] = check_selected(job['user']['username'])
    #         job['selection_possible'] = selection_possible(job['id'])
    #         print(job)
    #         jobs.append(job)
    # except Exception as e:
    #     print(e)
    # finally:
    #     cursor.close()
    #     conn.close()
    return render_template('list_applications_for_job.html', jobs = jobs)

@app.route('/make_payment/<job_id>')
@flask_login.login_required
def make_payment(job_id):
    if session['account_type'] == 'company':
        job = get_job_details_blockchain(str(job_id))
        payment = { 'id': get_transaction_details() + 1,
                    'job_id':job['id'],
                    'sender':job['createdby'],
                    'recipient': job['username'],
                    'amount': job['payment'],
                    'job_status': job['status']}
        transaction_data={'transaction':payment}
        index = blockchain.create_new_transaction(transaction_data)
        if index:
            result = mine(uuid4().hex)
        if result.get('status', False):
            print("Information is Mined")
        return redirect(url_for('show_job', job_id = int(job_id)))


@app.route('/mark_completed/<job_id>')
@flask_login.login_required
def mark_completed(job_id):
    job = get_job_details_blockchain(str(job_id))
    job['status'] = 'completed'
    transaction_data = {'job': job}
    index = blockchain.create_new_transaction(transaction_data)
    if index:
        result = mine(uuid4().hex)
    if result.get('status', False):
        print("Information is Mined")
    return redirect(url_for('show_job', job_id = int(job_id)))


@app.route('/mark_selected/<application_id>')
@flask_login.login_required
def mark_selected(application_id):
    # Block chain initailization
    application = get_application_details_blockchain(app_id = application_id)
    job = get_job_details_blockchain(str(application['job_id']))
    job['status'] = 'assigned'
    job['username'] = application['username']
    transaction_data = {'job': job}
    index = blockchain.create_new_transaction(transaction_data)
    if index:
        result = mine(uuid4().hex)

    if result.get('status', False):
        print("Information is Mined")
    return redirect(url_for('list_applications', job_id = int(application['job_id'])))


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


def check_db():
    global cursor, conn
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
        query = "CREATE TABLE users (" \
                "id int NOT NULL, " \
                "username varchar(50) NOT NULL, " \
                "first_name varchar(50), " \
                "last_name varchar(50), " \
                "passhash varchar(500), " \
                "account_type varchar(500), " \
                "created DATETIME DEFAULT CURRENT_TIMESTAMP, " \
                "KEY(username), PRIMARY KEY(id));"
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
        query = "CREATE TABLE jobs (" \
                "id int NOT NULL, " \
                "company_name varchar(255), " \
                "company_location varchar(255), " \
                "company_url varchar(255), " \
                "job_title varchar(255), " \
                "job_posting varchar(255), " \
                "application_instructions varchar(1000), " \
                "created DATETIME, " \
                "createdby varchar(50), " \
                "status varchar(50), " \
                "username varchar(50), " \
                "CONSTRAINT fk_key_1 FOREIGN KEY (createdby) " \
                "REFERENCES users (username) ON DELETE CASCADE ON UPDATE CASCADE, " \
                "CONSTRAINT fk_key_2 FOREIGN KEY (username) " \
                "REFERENCES users (username) ON DELETE CASCADE ON UPDATE CASCADE, " \
                "PRIMARY KEY(id));"
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
            query = "CREATE TABLE applications (" \
                    "id int, " \
                    "job_id int(11) NOT NULL, " \
                    "username varchar(45) NOT NULL, " \
                    "description varchar(255), " \
                    "dateofcreation DATETIME, " \
                    "CONSTRAINT fk_key_3 FOREIGN KEY (job_id) " \
                    "REFERENCES jobs (id) ON DELETE CASCADE ON UPDATE CASCADE, " \
                    "CONSTRAINT fk_key_4 FOREIGN KEY (username) " \
                    "REFERENCES users (username) ON DELETE CASCADE ON UPDATE CASCADE, " \
                    "KEY(id), PRIMARY KEY (job_id, username));"
            cursor.execute(query)
            conn.commit()
        finally:
            cursor.close()
            conn.close()


# Blocakchain API's
# @app.route('/mine', methods=['GET'])
def mine(user_address):
    print("node_address", node_address)
    block = blockchain.mine_block(user_address, node_address)

    response = {
        'status': True,
        'message': 'Successfully Mined the new Block',
        'block_data': block
        }
    return response


@app.route('/blockchain', methods = ['GET'])
def get_full_blockchain():
    response = {
        'chain': blockchain.get_serialized_chain
        }
    return render_template('chain.html', chain = response['chain'])


# For Sync with the other nodes
@app.route('/chain', methods = ['GET'])
def get_full_chain():
    response = {
        'chain': blockchain.get_serialized_chain
        }
    return jsonify(response)


# Set each servers neighbours:
# @app.route('/register-node/<port>', methods = ['GET'])
def register_node(port):
    try:
        file = str(port)+'.csv'
        node_data = pd.read_csv(file)
        blockchain.create_node(node_data['address'])
        response = {
            'status': True,
            'message': 'New nodes has been added',
            'node_count': len(blockchain.nodes),
            'nodes': list(blockchain.nodes),
            }
        return response
    except Exception as e:
        print(e)

# def chain_changed():
#     for node_address in blockchain.nodes:
#         try: 
#             requests.post("http://" + node_address +'/chain_check', data={'chain':1})
#         except Exception as e:
#             print(e)
#     return True

# @app.route('/chain-check', methods = ['GET','POST'])
# def chain_check():
#     pass

# @app.route('/sync-chain', methods = ['GET'])
def consensus():
    def get_neighbour_chains():
        neighbour_chains = []
        for node_address in blockchain.nodes:
            resp = requests.get(
                "http://" + node_address + url_for('get_full_chain')).json()
            chain = resp['chain']
            neighbour_chains.append(chain)
        return neighbour_chains

    neighbour_chains = get_neighbour_chains()
    if not neighbour_chains:
        return jsonify({'message': 'No neighbour chain is available','status':0})

    longest_chain = max(neighbour_chains, key = len)  # Get the longest chain

    if len(blockchain.chain) >= len(longest_chain):  # If our chain is longest, then do nothing
        response = {
            'message': 'Chain is already up to date',
            'status': 1
            }
    else:  # If our chain isn't longest, then we store the longest chain
        blockchain.chain = [blockchain.get_block_object_from_block_data(
            block) for block in longest_chain]
        response = {
            'message': 'Chain was replaced',
            'status':2
            }

    return response


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('-H', '--host', default = '0.0.0.0')
    parser.add_argument('-p', '--port', default = 5000, type = int)
    args = parser.parse_args()
    check_db()
    register_node(port=args.port)
    app.run(host = args.host, port = args.port, debug = True)
