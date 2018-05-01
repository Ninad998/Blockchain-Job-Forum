"""
Team: 
Ninad Tungare        U49815021
Harshad Nalla Reddy  U60360285
Chunar Singh         U10488522

"""
# Packages
import flask
import atexit
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
app.config['BLOCKCHAIN_LENGTH'] = 3
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
def user_loader(username):
    if get_user_details_blockchain(username = username):
        user = User()
        user.id = username
        return user
    return


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
        (diff.days / 365, "year", "years"), (diff.days / 30, "month", "months"), (diff.days / 7, "week", "weeks"),
        (diff.days, "day", "days"), (diff.seconds / 3600, "hour", "hours"), (diff.seconds / 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),)

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
    if isinstance(jobs, dict) and len(jobs) > 0:
        ret = True
    return ret


def get_blockchain_length():
    return len(blockchain.get_serialized_chain)


def snapshot_block():
    chain = blockchain.get_serialized_chain
    block_id = 0
    block_items = ['index', 'proof', 'previous_hash', 'body', 'creation', 'nonce', 'hash']
    if chain[block_id]:
        block_data = [str(chain[block_id][item]) for item in block_items]
        insert_block_db(block_data)
        if chain[block_id]['body']:
            if chain[block_id]['body'][0]['user']:
                user_data = ['id', 'username', 'first_name', 'last_name', 'password', 'account_type', 'created',
                             'wallet']
                user_block = [chain[block_id]['body'][0]['user'][user_item] for user_item in user_data]
                response = insert_user_db(user_block)
                if not response:
                    update_user_db(chain[block_id]['body'][0]['user'])
            if chain[block_id]['body'][0]['job']:
                job_data = ['id', 'company_name', 'company_location', 'company_url', 'job_title','job_posting', 'application_instructions', 'created', 'createdby','status', 'username', 'payment']
                job_block = [chain[block_id]['body'][0]['job'][job_item] for job_item in job_data]
                response = insert_job_db(job_block)
                if not response:
                    update_job_db(chain[block_id]['body'][0]['job'])

            if chain[block_id]['body'][0]['application']:
                application_data = ['id', 'job_id', 'username', 'description', 'dateofcreation']
                application_block = [chain[block_id]['body'][0]['application'][app_item] for app_item in
                                     application_data]
                response = insert_application_db(application_block)
                if not response:
                    update_application_db(chain[block_id]['body'][0]['application'])

            if chain[block_id]['body'][0]['transaction']:
                tran_data = ['id', 'job_id', 'sender', 'receiver', 'amount', 'job_status']
                tran_block = [chain[block_id]['body'][0]['transaction'][tran_item] for tran_item in tran_data]
                response = insert_transaction_db(tran_block)

            if chain[block_id]['body'][0]['message']:
                msg_data = ['id', 'sender', 'receiver', 'date', 'message']
                msg_block = [chain[block_id]['body'][0]['message'][msg_item] for msg_item in msg_data]
                response = insert_message_db(msg_block)
        blockchain.remove_block_in_chain(block_id)
    return True


def get_user_details_blockchain(user_id = '', username = ''):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e)
    chain = blockchain.get_serialized_chain
    count = 0
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('user'):
                count += 1
                if user_id:
                    if each_block['body'][0]['user']['id'] == int(user_id):
                        return deepcopy(each_block['body'][0].get('user'))
                elif username:
                    if each_block['body'][0]['user']['username'] == username:
                        return deepcopy(each_block['body'][0].get('user'))
    if user_id:
        response = get_user_details_db(user_id = int(user_id))
        if response:
            return deepcopy(response)
    elif username:
        response = deepcopy(get_user_details_db(username = username))
        if response:
            return deepcopy(response)
    else:
        response = get_user_details_db()
        if response and isinstance(response, int):
            count += response
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
            query = "SELECT * FROM users WHERE username = '%s';" % username
        else:
            query = "SELECT * FROM users;"
        cursor.execute(query)
        response = cursor.fetchall()
        if len(response) > 1:
            count = len(response)
        else:
            response = response[0]
            if response:
                user = {
                    'id': response[0],
                    'username': response[1],
                    'first_name': response[2],
                    'last_name': response[3],
                    'password': response[4],
                    'account_type': response[5],
                    'created': response[6],
                    'wallet': response[7],
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
    ret = False
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO users " \
                "(id, username, first_name, last_name, passhash, account_type, created, wallet) " \
                "VALUES %r;" % (tuple(user),)
        ret = cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return ret


def update_user_db(user):
    global cursor, conn
    ret = False
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "UPDATE users SET " \
                "username='%s', first_name='%s', last_name='%s', passhash='%s', " \
                "account_type='%s', created='%s', wallet=%s " \
                "WHERE id=%s;" % (user['username'], user['first_name'], user['last_name'],
                                  user['password'], user['account_type'], user['created'],
                                  user['wallet'], user['id'])
        ret = cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return ret


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
    if job_id:
        response = get_job_details_db(job_id = int(job_id))
        if response:
            return deepcopy(response)
    else:
        response = get_job_details_db()
        if response and isinstance(response, int):
            count += response
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
            response = response[0] 
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
                'payment': response[11],
            }

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    if count > 0:
        return count

    return job


def get_job_list(username = '', user = ''):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e)
    chain = blockchain.get_serialized_chain
    blockchain_job_list = []
    job_set = set()
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('job'):
                if each_block['body'][0]['job']['id'] not in job_set:
                    job_set.add(each_block['body'][0]['job']['id'])
                    if username:
                        if each_block['body'][0]['job']['createdby'] == username:
                            blockchain_job_list.append(each_block['body'][0].get('job'))
                    elif user:
                        if 'username' in each_block['body'][0]['job'] and each_block['body'][0]['job']['username'] == user:
                            blockchain_job_list.append(each_block['body'][0].get('job'))

                    else:
                        blockchain_job_list.append(each_block['body'][0].get('job'))
    if username:
        response = get_job_list_db(username = str(username))
        if response:
            for res in response:
                if res['id'] not in job_set:
                    job_set.add(res['id'])
                    blockchain_job_list.append(res)
    elif user:
        response = get_job_list_db(user = str(user))
        if response:
            for res in response:
                if res['id'] not in job_set:
                    job_set.add(res['id'])
                    blockchain_job_list.append(res)
    else:
        response = get_job_list_db()
        if response:
            for res in response:
                if res['id'] not in job_set:
                    job_set.add(res['id'])
                    blockchain_job_list.append(res)
    return blockchain_job_list


def get_job_list_db(username = '', user = ''):
    global cursor, conn
    jobs = list()
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if username:
            query = "SELECT * FROM jobs WHERE createdby LIKE '%s';" % username
        elif user:
            query = "SELECT * FROM jobs WHERE username LIKE '%s';" % user
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
                'payment': row[11],
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
    ret = False
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO jobs " \
                "(id, company_name, company_location, company_url, job_title, " \
                "job_posting, application_instructions, created, createdby, " \
                "status, username, payment) VALUES %r;" % (tuple(job),)
        ret = cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return ret


def update_job_db(job):
    global cursor, conn
    ret = False
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "UPDATE jobs SET " \
                "company_name='%s', company_location='%s', company_url='%s', job_title='%s', " \
                "job_posting='%s', application_instructions='%s', created='%s', createdby='%s', " \
                "status='%s', username='%s', payment=%s " \
                "WHERE id=%s;" % (job['company_name'], job['company_location'], job['company_url'],
                                  job['job_title'], job['job_posting'], job['application_instructions'],
                                  job['created'], job['createdby'], job['status'], job['username'],job['payment'],
                                  job['id'])
        ret = cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return ret


def get_application_details_blockchain(job_id = '', username = '', app_id = ''):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e)
    chain = blockchain.get_serialized_chain
    count = 0
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('application'):
                count += 1
                if app_id:
                    if int(each_block['body'][0]['application']['id']) == int(app_id):
                        return deepcopy(each_block['body'][0].get('application'))
                elif job_id and username:
                    if int(each_block['body'][0]['application']['job_id']) == int(job_id) and \
                            each_block['body'][0]['application']['username'] == username:
                        return deepcopy(each_block['body'][0].get('application'))
    if app_id:
        response = get_application_details_db(app_id = app_id)
        if response:
            return deepcopy(response)
    elif job_id and username:
        response = get_application_details_db(job_id = job_id, username = username)
        if response:
            return deepcopy(response)
    else:
        response = get_application_details_db()
        if response and isinstance(response, int):
            count += response
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
            query = "SELECT * FROM applications WHERE job_id = %s AND username LIKE '%s';" % (job_id, username)
        else:
            query = "SELECT * FROM applications;"
        cursor.execute(query)
        response = cursor.fetchall()
        if len(response) > 1:
            count = len(response)
        else:
            response = response[0]
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
    if job_id:
        response = get_application_list_db(job_id = int(job_id))
        if response:
            blockchain_application_list.extend(response)
    elif username:
        response = get_application_list_db(username = str(username))
        if response:
            blockchain_application_list.extend(response)
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
            query = "SELECT * FROM applications WHERE username LIKE '%s';" % username
        else:
            query = "SELECT * FROM applications;"
        cursor.execute(query)
        response = cursor.fetchall()
        for row in response:
            application = {
                'id': row[0],
                'job_id': row[1],
                'username': row[2],
                'description': row[3],
                'dateofcreation': row[4],
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
    ret = False
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO applications " \
                "(id, job_id, username, description, dateofcreation) " \
                "VALUES %r;" % (tuple(application),)
        ret = cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return ret


def update_application_db(application):
    global cursor, conn
    ret = False
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "UPDATE applications SET " \
                "job_id='%s', username='%s', description='%s', dateofcreation='%s' " \
                "WHERE id=%s;" % (application['job_id'], application['username'], application['description'],
                                  application['dateofcreation'], application['id'])
        ret = cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return ret


def get_transaction_details(job_id = "", username=""):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e)
    chain = blockchain.get_serialized_chain
    count = 0
    blockchain_tran_list = []
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('transaction'):
                count += 1
                if job_id:
                    if each_block['body'][0]['transaction']['job_id'] == int(job_id):
                        return deepcopy(each_block['body'][0].get('transaction'))
                if username:
                    if each_block['body'][0]['transaction']['receiver'] == username:
                        blockchain_tran_list.append(each_block['body'][0].get('transaction'))
                    if each_block['body'][0]['transaction']['sender'] == username:
                        blockchain_tran_list.append(each_block['body'][0].get('transaction'))
    if job_id:
        response = get_transaction_details_db(job_id = int(job_id))
        if response:
            return deepcopy(response)
    elif username:
        response = get_transaction_list_db(sender = str(username))
        if response:
            blockchain_tran_list.extend(response)

        response = get_transaction_list_db(receiver = str(username))
        if response:
            blockchain_tran_list.extend(response)
        return blockchain_tran_list
    else:
        response = get_transaction_details_db()
        if response:
            count += response
    return count


def get_transaction_details_db(job_id = ''):
    global cursor, conn
    transaction = dict()
    count = 0
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if job_id:
            query = "SELECT * FROM transactions WHERE job_id = %s;" % job_id
        else:
            query = "SELECT * FROM transactions;"
        cursor.execute(query)
        response = cursor.fetchall()
        if len(response) > 1:
            count = len(response)
        else:
            response = response[0]
            transaction = {
                'id': response[0],
                'job_id': response[1],
                'sender': response[2],
                'receiver': response[3],
                'amount': response[4],
                'status': response[5],
            }

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    if count > 0:
        return count

    return transaction


def get_transaction_list_db(sender = '', receiver = ''):
    global cursor, conn
    transactions = list()
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if sender:
            query = "SELECT * FROM transactions WHERE sender LIKE '%s';" % sender
        elif receiver:
            query = "SELECT * FROM transactions WHERE receiver LIKE '%s';" % receiver
        else:
            query = "SELECT * FROM transactions;"
        cursor.execute(query)
        response = cursor.fetchall()
        for row in response:
            transaction = {
                'id': row[0],
                'job_id': row[1],
                'sender': row[2],
                'receiver': row[3],
                'amount': row[4],
                'status': row[5],
            }
            transactions.append(transaction)

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    return transactions


def insert_transaction_db(transaction):
    global cursor, conn
    ret = False
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO transactions " \
                "(id, job_id, sender, receiver, amount, status) " \
                "VALUES %r;" % (tuple(transaction),)
        ret = cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return ret


def get_message_details(username = ""):
    # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e)
    chain = blockchain.get_serialized_chain
    count = 0
    blockchain_msg_list = []
    for each_block in reversed(chain):
        if each_block.get('body', []):
            if each_block['body'][0].get('message'):
                count += 1
                if username:
                    if each_block['body'][0]['message']['receiver'] == str(username):
                        blockchain_msg_list.append(each_block['body'][0].get('message'))
    if blockchain_msg_list:
        return blockchain_msg_list
    if username:
        response = get_message_list_db(receiver = str(username))
        if response:
            blockchain_msg_list.extend(response)
    else:
        response = get_message_details_db()
        if response and isinstance(response, int):
            count += response
    return count


def get_message_details_db(id = ''):
    global cursor, conn
    message = dict()
    count = 0
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if id:
            query = "SELECT * FROM messages WHERE id = %s;" % id
        else:
            query = "SELECT * FROM messages;"
        cursor.execute(query)
        response = cursor.fetchall()
        if len(response) > 1:
            count = len(response)
        else:
            response = response[0]
            message = {
                'id': response[0],
                'sender': response[1],
                'receiver': response[2],
                'date': response[3],
                'message': response[4],
            }

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    if count > 0:
        return count

    return message


def get_message_list_db(sender = '', receiver = ''):
    global cursor, conn
    messages = list()
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if sender:
            query = "SELECT * FROM messages WHERE sender LIKE '%s';" % sender
        elif receiver:
            query = "SELECT * FROM messages WHERE receiver LIKE '%s';" % receiver
        else:
            query = "SELECT * FROM messages;"
        cursor.execute(query)
        response = cursor.fetchall()
        for row in response:
            message = {
                'id': row[0],
                'sender': row[1],
                'receiver': row[2],
                'date': response[3],
                'message': response[4],
            }
            messages.append(message)

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    return messages


def insert_message_db(message):
    global cursor, conn
    ret = False
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO messages " \
                "(id, sender, receiver, sent, message) " \
                "VALUES %r;" % (tuple(message),)
        ret = cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return ret


def get_chain_list_db(index = ''):
    global cursor, conn
    chain = list()
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        if index:
            query = "SELECT * FROM chain WHERE id = %s;" % index
        else:
            query = "SELECT * FROM chain;"
        cursor.execute(query)
        response = cursor.fetchall()
        for row in response:
            block = {
                'index': row[0],
                'proof': row[1],
                'previous_hash': row[2],
                'body': row[3],
                'creation': row[4],
                'nonce': row[5],
                'hash': row[6],
            }
            chain.append(block)

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    return chain


def get_latest_chain_list_db():
    global cursor, conn
    chain = list()
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM chain ORDER BY id LIMIT %d;" % app.config['BLOCKCHAIN_LENGTH']
        cursor.execute(query)
        response = cursor.fetchall()
        for row in response:
            block = {
                'index': row[0],
                'proof': row[1],
                'prev_hash': row[2],
                'body': row[3],
                'creation': row[4],
                'nonce': row[5],
                'hash': row[6],
            }
            chain.append(block)

    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()

    return chain


def insert_block_db(block):
    global cursor, conn
    ret = False
    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "INSERT INTO chain " \
                "(id, proof, prev_hash, body, creation, nonce, hash) " \
                "VALUES %r;" % (tuple(block),)
        ret = cursor.execute(query)
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
        conn.close()
    return ret



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
    return render_template('home.html', jobs = jobs)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/create', methods = ['GET', 'POST'])
@flask_login.login_required
def create_job():
    if request.method == 'POST':
        company_url = str(request.form['company_url'])
        if company_url[:4] == 'http':
            company_ur = company_url
        else:
            company_ur = 'http://' + company_url
        
        # Block chain initailization
        transaction_data = {}
        job_form_data = {
            'id': get_job_details_blockchain() + 1, 'company_name': str(request.form['company_name']),
            'company_location': str(request.form['company_location']), 'company_url': company_ur,
            'job_title': str(request.form['job_title']), 'job_posting': str(request.form['job_posting']),
            'application_instructions': str(request.form['application_instructions']),
            'createdby': str(flask_login.current_user.id), 'created': str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            'status': 'not_selected', 'username': "NULL", 'payment': str(request.form['payment'])
        }
        transaction_data['job'] = job_form_data
        index = blockchain.create_new_transaction(transaction_data)
        if index:
            result = mine(uuid4().hex)
        if result.get('status', False):
            if get_blockchain_length() > app.config['BLOCKCHAIN_LENGTH']:
                snapshot_block()
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
            login_user(str(request.form['username']), str(request.form['account_type']))

            # Block chain initailization
            transaction_data = {}
            user_form_data = {
                'id': get_user_details_blockchain() + 1, 'username': str(request.form['username']),
                'first_name': str(request.form['first_name']), 'last_name': str(request.form['last_name']),
                'password': pbkdf2_sha256.hash(str(request.form['password'])),
                'account_type': str(request.form['account_type']),
                'created': str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")), 'wallet': 0,
            }
            transaction_data['user'] = user_form_data
            index = blockchain.create_new_transaction(transaction_data)
            if index:
                result = mine(uuid4().hex)

            if result.get('status', False):
                if get_blockchain_length() > app.config['BLOCKCHAIN_LENGTH']:
                    snapshot_block()
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
            user_details = get_user_details_blockchain(username = str(request.form['username']))
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


@app.route('/profile', methods = ['GET', 'POST'])
@flask_login.login_required
def profile():
    if request.method == 'POST':
        user_info = get_user_details_blockchain(username=str(flask_login.current_user.id)) 
        user_info['first_name'] = str(request.form['first_name'])
        user_info['last_name'] = str(request.form['last_name'])
        user_info['created'] = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        transaction_data = {'user': user_info}
        index = blockchain.create_new_transaction(transaction_data)
        if index:
            result = mine(uuid4().hex)

        if result.get('status', False):
            if get_blockchain_length() > app.config['BLOCKCHAIN_LENGTH']:
                snapshot_block()
        
            user_id = get_user_details_blockchain()
            
        flash(u'Profile was successfully updated.', 'success')
        return redirect(url_for('show_user', user_id = user_id))
    else:

        user = get_user_details_blockchain(username=str(flask_login.current_user.id))
        trans = get_transaction_details(username=str(flask_login.current_user.id))
        if user['account_type'] == 'company':
            amount = 100
        else: 
            amount = 0
        for each_trans in trans:
            if str(flask_login.current_user.id) == each_trans['receiver']:
                amount+=int(each_trans['amount'])
            elif str(flask_login.current_user.id) == each_trans['sender']:
                amount-=int(each_trans['amount'])
        user['wallet'] = amount
        return render_template('profile.html', user = user)


@app.route('/send_mail', methods = ['POST'])
def send_mail():
    msg = {
        'id': get_message_details() + 1, 'sender': str(request.form['from_msg']),
        'receiver': str(request.form['to_msg']), 'date': str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        'message': str(request.form['msg'])
    }
    transaction_data = {'message': msg}
    index = blockchain.create_new_transaction(transaction_data)
    if index:
        result = mine(uuid4().hex)
    if result.get('status', False):
        if get_blockchain_length() > app.config['BLOCKCHAIN_LENGTH']:
            snapshot_block()
        print("Information is Mined")
    flash(u'Message successfully sent.', 'success')
    return redirect(url_for('home'))


@app.route('/mail/<username>')
def mail(username):
    user = get_user_details_blockchain(username = str(username))  # dict
    mail_contacts = []
    if user['account_type'] == 'company':
        jobs = get_job_list(username = str(username))  # list
        for job in jobs:
            if job['status'] != "not_selected":
                mail_contacts.append(job['username'])

        mails = get_message_details(str(username))
        if not isinstance(mails, list):
            mails = []

    elif user['account_type'] == 'user':
        jobs = get_job_list(user = str(username))  # list
        for job in jobs:
            if job['status'] != "not_selected":
                mail_contacts.append(job['createdby'])

        mails = get_message_details(str(username))
        if not isinstance(mails, list):
            mails = []

    else:
        flash(u'Messaging is disabled.', 'success')
        return redirect(url_for('home'))

    return render_template('mail.html', user = user, mail_contacts = mail_contacts, mails = mails)


@app.route('/user/<user_id>')
def show_user(user_id):
    user = get_user_details_blockchain(user_id = str(user_id))
    return render_template('show_user.html', user = user)


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

        if check_applications(job_id, session.get('username')):
            applied = True

        if job['status'] == "completed":
            amt = get_transaction_details(str(job_id))
            if amt:
                payment = True

    return render_template('show_job.html', job = job, applied = applied, payment = payment)


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

    if request.method == 'GET':
        return render_template('apply.html', job = job)

    # Block chain initailization
    transaction_data = {}
    application_form_data = {
        'id': get_application_details_blockchain() + 1, 'job_id': str(job_id),
        'username': str(flask_login.current_user.id), 'description': str(request.form.get('desc')),
        'dateofcreation': str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    }
    transaction_data['application'] = application_form_data
    index = blockchain.create_new_transaction(transaction_data)
    if index:
        result = mine(uuid4().hex)

    if result.get('status', False):
        if get_blockchain_length() > app.config['BLOCKCHAIN_LENGTH']:
            snapshot_block()
        print("Information is Mined")
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
    return render_template('list_applications_by_user.html', jobs = jobs)


@app.route('/company')
@flask_login.login_required
def list_jobs():
    jobs = get_job_list(username = str(flask_login.current_user.id))
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
        job['user'] = get_user_details_blockchain(username = str(job['username']))
        if not job['select_possible']:
            if job_details['username'] == job['username']:
                job['user']['selected'] = True
            else:
                job['user']['selected'] = False
        if job_details['status'] == "completed":
            job['user']['completed'] = True
        else:
            job['user']['completed'] = False
        jobs.append(job)
    return render_template('list_applications_for_job.html', jobs = jobs)


@app.route('/make_payment/<job_id>')
@flask_login.login_required
def make_payment(job_id):
    if session['account_type'] == 'company':
        job = get_job_details_blockchain(str(job_id))
        payment = {
            'id': get_transaction_details() + 1, 'job_id': job['id'], 'sender': job['createdby'],
            'receiver': job['username'], 'amount': job['payment'], 'job_status': job['status']
        }
        transaction_data = {'transaction': payment}
        index = blockchain.create_new_transaction(transaction_data)
        if index:
            result = mine(uuid4().hex)
        if result.get('status', False):
            if get_blockchain_length() > app.config['BLOCKCHAIN_LENGTH']:
                snapshot_block()
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
        if get_blockchain_length() > app.config['BLOCKCHAIN_LENGTH']:
            snapshot_block()
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
        if get_blockchain_length() > app.config['BLOCKCHAIN_LENGTH']:
            snapshot_block()
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
                "wallet int, " \
                "created DATETIME, " \
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
                "payment int, " \
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
                "id int NOT NULL, " \
                "job_id int NOT NULL, " \
                "username varchar(50) NOT NULL, " \
                "description varchar(255), " \
                "dateofcreation DATETIME, " \
                "KEY(id), PRIMARY KEY (job_id, username));"
        cursor.execute(query)
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM transactions  LIMIT 1;"
        cursor.execute(query)
    except Exception as e:
        print(e)
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "CREATE TABLE transactions (" \
                "id varchar(50) NOT NULL, " \
                "job_id int NOT NULL, " \
                "sender varchar(50) NOT NULL, " \
                "receiver varchar(50) NOT NULL, " \
                "amount int NOT NULL, " \
                "status varchar(50), " \
                "PRIMARY KEY (id));"
        cursor.execute(query)
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM messages LIMIT 1;"
        cursor.execute(query)
    except Exception as e:
        print(e)
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "CREATE TABLE messages (" \
                "id varchar(50) NOT NULL, " \
                "sender varchar(50) NOT NULL, " \
                "receiver varchar(50) NOT NULL, " \
                "sent DATETIME NOT NULL, " \
                "message varchar(500) NOT NULL, " \
                "PRIMARY KEY (id));"
        cursor.execute(query)
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    try:
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "SELECT * FROM chain LIMIT 1;"
        cursor.execute(query)
    except Exception as e:
        print(e)
        db = getMysqlConnection()
        conn = db['conn']
        cursor = db['cursor']
        query = "CREATE TABLE chain (" \
                "id varchar(50) NOT NULL, " \
                "proof varchar(50) NOT NULL, " \
                "prev_hash varchar(100) NOT NULL, " \
                "body varchar(500) NOT NULL, " \
                "creation DATETIME NOT NULL, " \
                "nonce int NOT NULL, " \
                "hash varchar(100) NOT NULL, " \
                "PRIMARY KEY (id));"
        cursor.execute(query)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


# Blocakchain API's
def mine(user_address):
    block = blockchain.mine_block(user_address, node_address)
    response = {'status': True, 'message': 'Successfully Mined the new Block', 'block_data': block}
    return response


@app.route('/blockchain', methods = ['GET'])
def get_full_blockchain():
        # check for changes:
    try:
        consensus()
    except Exception as e:
        print(e)
    response = {'chain': blockchain.get_serialized_chain}
    return render_template('chain.html', chain = response['chain'])


# For Sync with the other nodes
@app.route('/chain', methods = ['GET'])
def get_full_chain():
    blockchain = blockchain.get_serialized_chain
    index =v0 
    if 'index' in  blockchain[-1]:
        index = blockchain[-1]['index']
    length = len(blockchain.chain) + len(get_chain_list_db())
    response = {'chain': blockchain.get_serialized_chain,'length':length,'index':index}
    print(response)
    return jsonify(response)


# Set each servers neighbours:
# @app.route('/register-node/<port>', methods = ['GET'])
def register_node():
    try:
        node_data = pd.read_csv('server.csv')
        blockchain.create_node(node_data['address'])
        response = {
            'status': True, 'message': 'New nodes has been added', 'node_count': len(blockchain.nodes),
            'nodes': list(blockchain.nodes),
        }
        return response
    except Exception as e:
        print(e)


# @app.route('/sync-chain', methods = ['GET'])
def consensus():
    def get_neighbour_chains():
        neighbour_chains = []
        neighbour_chain_length =[]
        neighbour_index = []
        for node_address in blockchain.nodes:
            resp = requests.get("http://" + node_address + url_for('get_full_chain')).json()
            chain = resp['chain']
            leng = resp['length']
            index = resp['index']
            neighbour_chains.append(chain)
            neighbour_chain_length.append(leng)
            neighbour_index.append(index)
        return neighbour_chains,neighbour_chain_length,neighbour_index

    neighbour_chains, neighbour_chain_length, neighbour_index = get_neighbour_chains()
    if not neighbour_chains:
        return jsonify({'message': 'No neighbour chain is available', 'status': 0})
    # Get the longest chain
    check = max(neighbour_chain_length)
    index_check = max(neighbour_index)
    longest_chain = neighbour_chains[neighbour_chain_length.index(check)]
    if longest_chain[-1]['index'] != index_check:
        longest_chain = neighbour_chains[neighbour_index.index(index_check)]
           
    print(longest_chain,index_check,check)
    # longest_chain = max(neighbour_chains, key = len)
    length = len(blockchain.chain) + len(get_chain_list_db())
    if length >= len(longest_chain):  # If our chain is longest, then do nothing
        response = {'message': 'Chain is already up to date', 'status': 1}
    else:  # If our chain isn't longest, then we store the longest chain
        blockchain.chain = [blockchain.get_block_object_from_block_data(block) for block in longest_chain]
        response = {'message': 'Chain was replaced', 'status': 2}

    return response


def exit_handler():
    print('My application is ending!')
    chain_length= get_blockchain_length()
    for _ in range(chain_length):
        snapshot_block()      
    print('snapshot completed')

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('-H', '--host', default = '0.0.0.0')
    parser.add_argument('-p', '--port', default = 5000, type = int)
    args = parser.parse_args()
    check_db()
    register_node()
    app.run(host = args.host, port = args.port, debug = True, threaded = True)
    # atexit.register(exit_handler)