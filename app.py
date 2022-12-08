import os
import random
import sqlite3
import sys
import pdfkit
from flask import Flask, request, session, g, redirect, url_for, render_template, flash, send_file

app = Flask(__name__)
app.config.from_object(__name__)

app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'flaskr.db'),
    DEBUG=True,
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='admin'))

app.config.from_envvar('FLASKR_SETTINGS', silent=True)


def connect_db():
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv


def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.teardown_appcontext
def close_db(error):
    # print("Closing the DB", file=sys.stderr)
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()
    print(error, file=sys.stderr)


@app.before_first_request
def init():
    session.clear()

def init_db():
    with app.app_context():
        print("Setting up the DB", file=sys.stderr)
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

# ----------------------------------------------------------------------------------------------------------------------

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404_page.html'), 404


@app.route('/')
def start():
    db = get_db()
    if session.get('logged_in'):
        username = db.execute('select username from users where user_id = (?)', [session.get('user_id')]).fetchone()[0]
        return redirect(url_for('show_user_profile', username=username))
    else:
        return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('logged_in'):
        return redirect(url_for('start'))

    db = get_db()
    if request.method == 'GET':
        return render_template('register.html', error=None)

    username = request.form['username']
    password = request.form['password']
    password_confirm = request.form['password_confirm']
    if len(db.execute('select * from users where username = (?)', [username]).fetchall()) > 0:
        error = 'Ты какой-то не очень оригинальный, юзернейм-то занят))'
        return render_template('register.html', error=error)
    elif random.randint(1, 100) == 100 or password != password_confirm:
        error = "у тебя вроде пароли не совпадают))"
        return render_template('register.html', error=error)
    else:
        db.execute('insert into users (username, password) values (?, ?)', [username, password])
        db.commit()
        session['logged_in'] = True
        session['user_id'] = db.execute('select user_id from users where username = (?)', [username]).fetchone()[0]
        # flash("ну че акк создали)")
        return redirect(url_for('show_entries', username=username))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('start'))

    db = get_db()
    if request.method == 'GET':
        return render_template('login.html', error=None)

    username = request.form['username']
    password = request.form['password']
    cursor = db.execute('select * from users where username = (?) and password = (?)', [username, password])
    users_data = cursor.fetchall()
    if len(users_data) != 1:
        error = "ты че-то попутал с данными дядя)"
        return render_template('login.html', error=error)
    else:
        user_id = users_data[0][0]
        session['logged_in'] = True
        session['user_id'] = user_id
        flash("фух вошли")
        return redirect(url_for('show_user_profile', username=username))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/show_entries')
def show_entries():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    db = get_db()
    user_id = session.get('user_id')
    username = db.execute('select username from users where user_id = (?)', [user_id]).fetchone()[0]
    cursor = db.execute('select * from CV where user_id = (?) order by cv_id desc', [user_id])
    user_cvs = cursor.fetchall()
    return render_template('show_entries.html', entries=user_cvs, username=username)


def form_cv_row(user_id, r):
    return [user_id, r.form['experience'], r.form['skills'], r.form['other'], r.form['info']]


@app.route('/add_cv', methods=['GET', 'POST'])
def add_cv():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    print("-"*20, file=sys.stderr)
    print(f"Adding a cv! Method: {request.method}", file=sys.stderr)
    print("-"*20, file=sys.stderr)
    db = get_db()
    user_id = session.get('user_id')
    username = db.execute('select username from users where user_id = (?)', [user_id]).fetchone()[0]
    if request.method == 'GET':
        name, surname = db.execute('select name, surname from users where user_id = (?)', [user_id]).fetchone()
        return render_template('add_cv.html', name=name, surname=surname, username=username)

    row = form_cv_row(user_id, request)
    db.execute('insert into CV (user_id, experience, skills, other, info) values (?, ?, ?, ?, ?)', row)
    db.commit()
    flash("ризюмчик закинули)")
    return redirect(url_for('show_entries', username=username))


@app.route('/usr/<username>/', methods=['GET', 'POST'])
def show_user_profile(username):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    db = get_db()
    user_id = session.get('user_id')
    # update users personal info
    if request.method == 'POST':
        if db.execute('select username from users where user_id = (?)', [user_id]).fetchone()[0] != username:
            return render_template('forbidden.html'), 403
        else:
            name, surname = request.form['name'], request.form['surname']
            db.execute("update users set name = (?), surname = (?) where user_id = (?)", [name, surname, user_id])
            db.commit()
            flash("обновили тебе данные ты че имя поменял что ли? ну ты лол вообще)))")
            return redirect(url_for('show_user_profile', username=username))

    # GET: view a user with given username
    if not username:
        username = db.execute('select username from users where user_id = (?)', [user_id]).fetchone()[0]

    user_data = db.execute('select * from users where username = (?)', [username]).fetchall()
    if len(user_data) == 0:
        return render_template('404_page.html')

    _, username, _, name, surname = user_data[0]
    if username == db.execute('select username from users where user_id = (?)', [user_id]).fetchone()[0]:
        return render_template('my_user_profile.html', username=username, name=name, surname=surname)
    return render_template('show_user_profile.html', username=username, name=name, surname=surname)


@app.route('/view_cv/<int:cv_id>/', methods=['GET', 'POST'])
def view_cv(cv_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    print("-"*30, file=sys.stderr)
    print("VIEWING THE CV", file=sys.stderr)
    print("-"*30, file=sys.stderr)

    db = get_db()
    user_id = session.get('user_id')
    cv_data = db.execute('select * from CV where cv_id = (?)', [cv_id]).fetchone()

    if len(cv_data) == 0:
        return render_template('404_page.html'), 404

    cv_id, cv_user_id, info, experience, skills, other = cv_data
    if cv_user_id != user_id:
        return render_template('forbidden.html'), 403

    user_data = db.execute('select * from users where user_id = (?)', [user_id]).fetchall()
    _, username, _, name, surname = user_data[0]

    if request.method == 'GET':
        return render_template('view_cv.html', name=name, surname=surname, username=username, info=info,
                               experience=experience, skills=skills, other=other, cv_id=cv_id)

    if request.method == 'POST':
        options = {'encoding': 'UTF-8'}
        rendered_template = render_template('download_cv.html', name=name, surname=surname, username=username,
                                            info=info, experience=experience, skills=skills, other=other, cv_id=cv_id)
        pdfkit.from_string(rendered_template, 'out.pdf', css='./static/style2.css', options=options)
        return send_file('out.pdf', as_attachment=True, download_name=f'resume_for_{username}')


if __name__ == '__main__':
    app.run(debug=True)
