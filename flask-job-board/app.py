"""
Team: 
Ninad Tungare        U49815021
Harshad Nalla Reddy  U
Chunar Singh         U

"""
# Packages
import flask
import requests
import settings
import flask_login
import pandas as pd
from uuid import uuid4
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
def timesince(dt, default = "just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    """
    f = '%Y-%m-%d %H:%M:%S'
    print("date", dt)
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
    user.id = str(request.form['username'])
    flask_login.login_user(user)
    session['username'] = flask_login.current_user.id
    session['logged_in'] = True
    session['account_type'] = account_type


def check_applications(username):
    ret = False
    try:
        user = str(flask_login.current_user.id)
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM applications WHERE username LIKE '%%%s%%';" % user
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


def get_user_details_blockchain(user_id = ''):
    chain = blockchain.get_serialized_chain
    print("user_id", user_id)
    blockchain_user_list = []
    for each_block in chain:
        if each_block.get('body', []):
            if not each_block['body'][0].get('application') and not each_block['body'][0].get('job'):
                if user_id:
                    if each_block['body'][0]['user']['id'] == int(user_id):
                        blockchain_user_list.append(each_block['body'][0].get('user'))
                        break
                else:
                    blockchain_user_list.append(each_block['body'][0].get('user'))
    return blockchain_user_list


def get_job_details_blockchain(job_id = ''):
    chain = blockchain.get_serialized_chain
    print("chain", chain)
    blockchain_job_list = []
    for each_block in chain:
        if each_block.get('body', []):
            if not each_block['body'][0].get('application') and each_block['body'][0].get('job'):
                if job_id:
                    if each_block['body'][0]['job']['id'] == int(job_id):
                        blockchain_job_list.append(each_block['body'][0].get('job'))
                        break
                else:
                    blockchain_job_list.append(each_block['body'][0].get('job'))
    return blockchain_job_list


def generatejob(response):
    if flask_login.current_user.is_authenticated:
        allow_apply = not flask_login.current_user.id == response[8]
        allow_apply = allow_apply and not check_applications(
            flask_login.current_user.id)
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
    jobs = list()
    response = get_job_details_blockchain()
    if response:
        jobs = response
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
        transaction_data = {'user': {"username": str(session.get('username'))}}
        job_form_data = {
            'company_name': str(request.form['company_name']),
            'company_location': str(request.form['company_location']),
            'company_url': company_ur,
            'job_title': str(request.form['job_title']),
            'job_posting': str(request.form['job_posting']),
            'application_instructions': str(request.form['application_instructions']),
            'createdby': flask_login.current_user.id,
            'created': str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            'id': len(get_job_details_blockchain())
            }
        print("job_form_data", job_form_data)
        transaction_data['job'] = job_form_data
        index = blockchain.create_new_transaction(transaction_data)
        print("index", index)
        # NOTE: Can be used later
        response = {
            'message': 'Job has been successfully created',
            'block_index': index
            }
        if index:
            result = mine()
        if result.get('status', False):
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
            # according to blockchain
            next_url = len(get_job_details_blockchain()) - 1
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
                'id': len(get_user_details_blockchain()),
                'username': str(request.form['username']),
                'first_name': str(request.form['first_name']),
                'last_name': str(request.form['last_name']),
                'password': pbkdf2_sha256.hash(str(request.form['password'])),
                'account_type': str(request.form['account_type'])
                }
            transaction_data['user'] = user_form_data
            index = blockchain.create_new_transaction(transaction_data)
            print("index", index)
            # NOTE: Can be used later
            response = {
                'message': 'User Account has been successfully created',
                'block_index': index
                }

            # Prompt message to user can be given to confirm the mine of blockchain.
            if index:
                result = mine()

            if result.get('status', False):
                try:
                    db = getMysqlConnection()
                    conn = db['conn']
                    cursor = db['cursor']
                    query = "INSERT INTO users " \
                            "(id, username, first_name, last_name, passhash, account_type)" \
                            "VALUES %r;" % tuple(userlist)
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

                # according to blockchian:
                user_id = len(get_user_details_blockchain()) - 1
                flash(u'Successfully created new user.', 'success')
                return redirect(url_for('show_user', user_id = user_id))
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
        try:
            user_details = get_user_details_blockchain()
            for user in user_details:
                if user:
                    if user['username'] == str(request.form['username']):
                        username = user['username']
                        password = user['password']
                        account_type = user['account_type']
                        break
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

        if not pbkdf2_sha256.verify(request.form['password'], password):
            flash(u'Password or Username is incorrect.', 'error')
            return render_template('login.html')
        else:
            login_user(username, account_type)
            flash(u'You have been successfully logged in.', 'success')
            return redirect(next or url_for('home'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    flask_login.logout_user()
    session.pop('username')
    session.pop('logged_in')
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
    response = get_user_details_blockchain(str(user_id))
    print("user response", response)
    if response and isinstance(response, list):
        user = response[0]
    else:
        user = response
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
    return True


def check_selected(username):
    # TODO
    return True


@app.route('/job/<job_id>')
def show_job(job_id):
    response = get_job_details_blockchain(str(job_id))
    if response and isinstance(response, list):
        job = response[0]
    else:
        job = response

    applied = False
    selected = False
    if job:
        if flask_login.current_user.is_authenticated:
            allow_apply = not flask_login.current_user.id == job['createdby']
            allow_apply = allow_apply and not check_applications(
                flask_login.current_user.id)
            applied = check_applied(flask_login.current_user.id)
            if applied:
                selected = check_selected(flask_login.current_user.id)
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

    return render_template('show_job.html', job = job, applied = applied, selected = selected)


@app.route('/apply/<job_id>', methods = ['GET', 'POST'])
@flask_login.login_required
def apply(job_id):
    response = get_job_details_blockchain(str(job_id))
    if response and isinstance(response, list):
        job = response[0]
    else:
        job = response

    if job:
        if flask_login.current_user.is_authenticated:
            allow_apply = not flask_login.current_user.id == job['createdby']
            allow_apply = allow_apply and not check_applications(
                flask_login.current_user.id)
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

    try:
        db = getMysqlConnection()
        username = session['username']
        desc = request.form.get('desc')
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO applications " \
                "(jobid, username, description) " \
                "VALUES (\"%s\", \"%s\", \"%s\");" % (job_id, username, desc)

        result = cursor.execute(query)
        conn.commit()

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

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
    jobs = list()
    try:
        user = str(flask_login.current_user.id)
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT DISTINCT jobid FROM applications WHERE username LIKE '%%%s%%';" % user
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
    return render_template('list_applications_by_user.html', jobs = jobs)


@app.route('/company')
@flask_login.login_required
def list_jobs():
    jobs = get_job_details_blockchain()
    print("jobs", jobs)
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


def selection_possible(job_id):
    # TODO
    return False


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
            job['desc'] = item[3]
            job['dateofcreation'] = item[4]
            query = "SELECT * FROM users WHERE username='%s';" % str(item[2])
            result = cursor.execute(query)
            response = cursor.fetchone()
            job['user'] = getuser(response)
            job['user']['selected'] = check_selected(job['user']['username'])
            job['selection_possible'] = selection_possible(job['id'])
            print(job)
            jobs.append(job)
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return render_template('list_applications_for_job.html', jobs = jobs)


@app.route('/mark_completed/<job_id>')
@flask_login.login_required
def mark_completed(job_id):
    # TODO
    pass


@app.route('/mark_selected/<user_id>')
@flask_login.login_required
def mark_selected(user_id):
    # TODO
    pass


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


# Blocakchain API's
# @app.route('/mine', methods=['GET'])
def mine():
    print("node_address", node_address)
    block = blockchain.mine_block(node_address)

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
@app.route('/register-node', methods = ['GET'])
def register_node():
    node_data = pd.read_csv('servers.csv')
    print(node_data['address'].values.tolist())
    blockchain.create_node(node_data['address'])

    response = {
        'message': 'New nodes has been added',
        'node_count': len(blockchain.nodes),
        'nodes': list(blockchain.nodes),
        }
    return jsonify(response), 201


@app.route('/sync-chain', methods = ['GET'])
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
        return jsonify({'message': 'No neighbour chain is available'})

    longest_chain = max(neighbour_chains, key = len)  # Get the longest chain

    if len(blockchain.chain) >= len(longest_chain):  # If our chain is longest, then do nothing
        response = {
            'message': 'Chain is already up to date',
            'chain': blockchain.get_serialized_chain
            }
    else:  # If our chain isn't longest, then we store the longest chain
        blockchain.chain = [blockchain.get_block_object_from_block_data(
            block) for block in longest_chain]
        response = {
            'message': 'Chain was replaced',
            'chain': blockchain.get_serialized_chain
            }

    return jsonify(response)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('-H', '--host', default = '0.0.0.0')
    parser.add_argument('-p', '--port', default = 5000, type = int)
    args = parser.parse_args()
    check_db()
    app.run(host = args.host, port = args.port, debug = True)
