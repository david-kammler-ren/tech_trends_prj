import sqlite3
import logging

from flask import Flask, jsonify, json, render_template, request, url_for, redirect, flash
from werkzeug.exceptions import abort


db_connection_cnt_gbl = 0


# Function to get a database connection.
# This function connects to database with the name `database.db`
def get_db_connection():
    global db_connection_cnt_gbl
    connection = sqlite3.connect('database.db')
    db_connection_cnt_gbl += 1
    connection.row_factory = sqlite3.Row
    return connection


def close_db_connection(connection: sqlite3.Connection):
    global db_connection_cnt_gbl
    connection.close()
    db_connection_cnt_gbl -= 1


# Function to get a post using its ID
def get_post(post_id):
    connection = get_db_connection()
    post = connection.execute('SELECT * FROM posts WHERE id = ?',
                        (post_id,)).fetchone()
    close_db_connection(connection)
    return post


# Define the Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your secret key'


# Define the main route of the web application
@app.route('/')
def index():
    connection = get_db_connection()
    posts = connection.execute('SELECT * FROM posts').fetchall()
    close_db_connection(connection)
    return render_template('index.html', posts=posts)


# Define how each individual article is rendered
# If the post ID is not found a 404 page is shown
@app.route('/<int:post_id>')
def post(post_id):
    post = get_post(post_id)
    if post is None:
        app.logger.info(f'Attempt to access non-existing article with ID {post_id}! Returning with 404 error.')
        return render_template('404.html'), 404
    else:
        title = post["title"]
        app.logger.info(f'Article "{title}" retrieved!')
        return render_template('post.html', post=post)


# Define the About Us page
@app.route('/about')
def about():
    app.logger.info('"Abbout Us" page retrieved!')
    return render_template('about.html')


# Define the post creation functionality
@app.route('/create', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        else:
            connection = get_db_connection()
            connection.execute('INSERT INTO posts (title, content) VALUES (?, ?)',
                         (title, content))
            connection.commit()
            close_db_connection(connection)
            app.logger.info(f'Article "{title}" created!')
            return redirect(url_for('index'))

    return render_template('create.html')


# Health check returning simple HTTP 200 JSON response
@app.route('/healthz')
def healthz():
    # try to access the database
    db_okay = True
    # check that DB can be accessed (exists)
    try:
        connection = get_db_connection()
    except sqlite3.OperationalError:
        db_okay = False
    else:
        # check that posts table is available
        list_of_tables = connection.execute(
                    """SELECT name FROM sqlite_master WHERE type='table' AND name='posts'; """).fetchall()
        if not list_of_tables:
            db_okay = False
    if db_okay:
        response = app.response_class(
                response=json.dumps({"result": "OK - healthy"}),
                status=200,
                mimetype='application/json'
        )
    else:
        response = app.response_class(
                response=json.dumps({"result": "ERROR - unhealthy"}),
                status=500,
                mimetype='application/json'
        )
    return response


# Providing metrics on
# - concurrently active DB connections at the time
# - count of the posts in the DB
@app.route('/metrics')
def metrics():
    global db_connection_cnt_gbl
    connection = get_db_connection()
    post_cbt = connection.execute('SELECT COUNT(*) FROM posts').fetchone()[0]
    close_db_connection(connection)

    response = app.response_class(
            response=json.dumps(
                {
                    "db_connection_count": db_connection_cnt_gbl,
                    "post_count": post_cbt,
                }),
            status=200,
            mimetype='application/json'
    )
    return response


# start the application on port 3111
if __name__ == "__main__":
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": r"[{levelname:<8s}] [{asctime}] [{name}:{lineno:>4}]    {message}",
                        'datefmt': r'%Y-%m-%d %H:%M:%S %z',
                        'style': '{'},
        },
        "handlers": {
            "default": {
                "level": "DEBUG",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",  # Default is stderr
            }
        }
    }
    #logging.config.dictConfig(LOGGING_CONFIG)
    logging.basicConfig(format=r"[{levelname:<8s}] [{asctime}] [{name}:{lineno:>4}]    {message}",
                        datefmt=r'%Y-%m-%d %H:%M:%S %z', style='{', level=logging.DEBUG)
    app.run(host='0.0.0.0', port=3111)
