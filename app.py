import os
import datetime
from functools import wraps
from flask import (
    Flask, flash, render_template, 
    redirect, request, session, url_for)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

if os.path.exists("env.py"):
    import env


app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


def login_required(f):
    """
    Decorator to check if a user is currently logged in and redirect to the
    login page if not.
    Based on this function from the Flask documetation:
    https://flask.palletsprojects.com/en/2.0.x/patterns/viewdecorators/#login-required-decorator
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user") is None:
            flash("You must login to access this page.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def home():
    """
    If user is logged in, redirects them to workout_log page. Otherwise,
    renders the home page.
    """
    # check if user is currently logged in
    if session.get("user") is None:
        return render_template("home.html", page_title="Home")

    # redirect already logged in users to workout_log page
    return redirect(url_for("workout_log"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    GET: If user is logged in, redirects them to workout_log page. Otherwise,
    renders the login page.
    POST: Collects submitted user credentials.
    If username and passsword are correct, user is logged in and redirected to
    the home page.
    If username and password are incorrect, user is redirected to the login
    page.
    """
    # check if user is currently logged in
    if session.get("user") is None:
        if request.method == "POST":
            # assign submitted username to a variable and query the database to
            # find a record with that name
            username = request.form.get("username").lower()
            valid_username = mongo.db.users.find_one({"username": username})

            # check the submitted username exists in the database
            if valid_username:

                # check the submitted password matches the database
                if check_password_hash(
                        valid_username["password"],
                        request.form.get("password")):

                    # add user to session cookie and redirect to workout log
                    session["user"] = username
                    flash(f"Welcome, {username}")
                    return redirect(url_for('workout_log'))

                # if submitted password is incorrect, return to login page
                flash("Username or password incorrect. Please try again.")
                return redirect(url_for('login'))

            # if submitted username is incorrect, return to login page
            flash("Username or password incorrect. Please try again.")
            return redirect(url_for('login'))

        return render_template("login.html", page_title="Login")

    # redirect already logged in users to workout_log page
    return redirect(url_for("workout_log"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    GET: If user is logged in, redirects them to workout_log page. Otherwise,
    renders the registration page.
    POST: Collects submitted user data and checks if requested username is
    available.
    If username is taken, user is returned to the registration page.
    If username is available, a new user record is added to the users database
    and the user is logged in and redirected to the home page.
    """
    # check if user is currently logged in
    if session.get("user") is None:
        if request.method == "POST":
            # assign submitted username to a variable and check if it exists in
            # the database
            username = request.form.get("username").lower()
            duplicate_user = mongo.db.users.find_one({"username": username})

            # if username already exists, return user to registration page
            if duplicate_user:
                flash(f"Username \"{username}\" is unavailable.")
                return redirect(url_for("register"))

            # build dictionary with user submitted details
            new_user = {
                "username": username,
                "email": request.form.get("email"),
                "password": generate_password_hash(
                                request.form.get("password"))
            }

            # insert new user dict to users database
            mongo.db.users.insert_one(new_user)

            # add new user to session cookie and redirect to workout log
            session["user"] = username
            flash(
                f"Welcome, {session['user']}! Your account has been created.")
            return redirect(url_for('workout_log'))

        return render_template("register.html", page_title="Register")

    # redirect logged in users to workout_log page
    return redirect(url_for("workout_log"))


@app.route('/logout')
@login_required
def logout():
    """
    Removes the user from the session cookie and redirects to the home page.
    """
    session.pop("user")
    flash("You have been logged out.")
    return redirect(url_for('home'))


@app.route('/workout_log')
@login_required
def workout_log():
    """
    Finds all workouts logged by the user and renders the workout log page.
    """
    # if URL contains a date_from parameter
    if request.args.get("date_from"):
        # collect date_from and date_to values from query parameter and try to
        # convert to datetime objects
        try:
            date_from = datetime.datetime.strptime(
                                    request.args.get("date_from"), "%d/%m/%y")
            date_to = datetime.datetime.strptime(
                                    request.args.get("date_to") + "23:59:59",
                                    "%d/%m/%y%H:%M:%S")
        except ValueError:
            # if either of the submitted dates aren't valid and in the correct
            # format, redirect user back to workout_log page with error message
            flash(
                "Invalid date. Please enter valid dates in the format "
                "dd/mm/yy.")
            return redirect(url_for("workout_log"))

        # pass date_from and date_to objects into database query
        logs = list(mongo.db.workout_logs.aggregate([
            {
                "$match": {
                    "username": session['user'],
                    "date": {
                        "$gte": date_from,
                        "$lt": date_to
                    }
                }
            },
            {
                "$lookup": {
                    "from": "routines",
                    "localField": "routine_id",
                    "foreignField": "_id",
                    "as": "routine"
                }
            },
            {
                "$sort": {
                    "date": -1
                }
            }
            ]))
        # pass the results of the query to the workout_log template
        return render_template('workout_log.html', page_title="Workout Log",
                               logs=logs)

    # find all workouts logged by the current user
    # lookup corresponding routine details using routine_id
    logs = list(mongo.db.workout_logs.aggregate([
        {
            "$match": {
                "username": session['user'],
            }
        },
        {
            "$lookup": {
                "from": "routines",
                "localField": "routine_id",
                "foreignField": "_id",
                "as": "routine"
            }
        },
        {
            "$sort": {
                "date": -1
            }
        }
        ]))
    # pass the results of the query to the workout_log template
    return render_template('workout_log.html', page_title="Workout Log",
                           logs=logs)


@app.route("/add_workout", methods=["GET", "POST"])
@login_required
def add_workout():
    """
    GET: Renders the Add Workout page
    POST: Collects user input, inserts to workout_logs database and redirects
    user to Workout Log page
    """
    if request.method == "POST":
        # concatenate date picker value and time picker value
        date = request.form.get("workout_date") + request.form.get(
                "workout_time")
        # try to convert concatenated date into ISODate
        try:
            iso_date = datetime.datetime.strptime(date, "%d/%m/%y%H:%M")
        except ValueError:
            # if either the date or the time isn't valid and in the correct
            # format, redirect user back to add_workout page with error message
            flash(
                "Invalid date/time. Please enter a valid date and time in the "
                "formats dd/mm/yy and hh:mm.")
            return redirect(url_for("add_workout"))

        # build dictionary containing user submitted workout details
        entry = {
            "routine_id": ObjectId(request.form.get("routine_name")),
            "date": iso_date,
            "notes": request.form.get("notes"),
            "sets": int(request.form.get("sets")),
            "username": session['user']
        }

        # insert dictionary into database and redirect user to workout log
        mongo.db.workout_logs.insert_one(entry)
        flash("Workout record added!")
        return redirect(url_for("workout_log"))

    # retrieve routine_name query parameter, if present
    routine_name = request.args.get('routine_name')

    # find default routines (created by admin) and convert cursor to a list
    default_routines = list(mongo.db.routines.find({"username": "admin"}))
    # find user's custom routines and convert cursor to a list
    user_routines = list(mongo.db.routines.find({"username": session['user']}))

    # concatenate default and custom routines lists, then pass with
    # routine_name to the add_workout template
    routines = default_routines + user_routines
    return render_template(
        "add_workout.html", page_title="Add Workout", routines=routines,
        routine_name=routine_name)


@app.route("/edit_workout/<log_id>", methods=["GET", "POST"])
@login_required
def edit_workout(log_id):
    """
    GET: Renders edit_workout page with data from requested log id
    POST: If current user created the log entry, updates the entry.
    Otherwise, returns user to workout log page.
    """
    if request.method == "POST":
        # find log entry to edit from database
        log = mongo.db.workout_logs.find_one({"_id": ObjectId(log_id)})

        # check current user is the user who created the entry
        if log["username"] == session["user"]:
            # concatenate date picker value and time picker value
            date = request.form.get("workout_date") + request.form.get(
                    "workout_time")
            # convert concatenated date into ISODate
            iso_date = datetime.datetime.strptime(date, "%d/%m/%y%H:%M")

            # build dictionary from user submitted workout details
            entry = {
                "routine_id": ObjectId(request.form.get("routine_name")),
                "date": iso_date,
                "notes": request.form.get("notes"),
                "sets": int(request.form.get("sets")),
                "username": session['user']
            }

            # update the database entry with the entered details and redirect
            # user to workout log
            flash("Workout record updated.")
            mongo.db.workout_logs.update_one(log, {"$set": entry})
            return redirect(url_for("workout_log"))

        # redirect unauthorised users to workout log page
        flash("You don't have permission to edit this log.")
        return redirect(url_for("workout_log"))

    # find log entry to edit from database
    log = mongo.db.workout_logs.find_one({"_id": ObjectId(log_id)})
    # find default routines (created by admin) and convert cursor to a list
    default_routines = list(mongo.db.routines.find({"username": "admin"}))
    # find user's custom routines and convert cursor to a list
    user_routines = list(mongo.db.routines.find({"username": session['user']}))
    # concatenate default and custom routines lists, then pass to the
    # edit_workout template
    routines = default_routines + user_routines
    return render_template(
        "edit_workout.html", page_title="Edit Workout",
        log=log, routines=routines)


@app.route("/delete_workout/<log_id>")
@login_required
def delete_workout(log_id):
    """
    Checks if current user created the log entry to be deleted and deletes it
    if so. Otherwise, returns user to workout log page.
    """
    # find log entry to edit from database
    log = mongo.db.workout_logs.find_one({"_id": ObjectId(log_id)})

    # check current user is the user who created the entry
    if log["username"] == session["user"]:
        # delete log entry from database and redirect user to workout log
        mongo.db.workout_logs.delete_one(log)
        flash("Workout record deleted.")
        return redirect(url_for("workout_log"))

    # redirect unauthorised users to workout log page
    flash("You don't have permission to delete this log.")
    return redirect(url_for("workout_log"))


@app.route("/my_routines")
@login_required
def my_routines():
    """
    Finds all default (admin created) routines and all routines created by the
    user and renders the my_routines page
    """
    # query database to find all admin created routines
    default_routines = list(mongo.db.routines.find({"username": "admin"}))
    # query database to find all routines created by current user
    custom_routines = list(mongo.db.routines.find(
                        {"username": session["user"]}))
    # pass default and custom routines to the my_routines template
    return render_template("my_routines.html", page_title="My Routines",
                           default_routines=default_routines,
                           custom_routines=custom_routines)


@app.route("/add_routine", methods=["GET", "POST"])
@login_required
def add_routine():
    """
    GET: Render the add_routine page
    POST: Checks if the submitted routine name is the same as any admin
    routines or routines by the current. If so, user is redirected back to the
    add_routine page. If not, the routine is added to the database.
    """
    if request.method == "POST":
        # assign submitted routine name to a variable and check if the current
        # user or admin already has a routine of this name
        routine_name = request.form.get("routine_name")
        duplicate_routine = mongo.db.routines.find_one(
            {
                "$or": [
                    {
                        "username": session["user"],
                        "routine_name": routine_name
                    },
                    {
                        "username": "admin",
                        "routine_name": routine_name
                    }
                ]
            })

        # if a record is found matching user and routine name, redirect
        # to add_routine page
        if duplicate_routine:
            flash(
                "Duplicate routine name. Please enter a unique routine name.")
            return redirect(url_for("add_routine"))

        # build dictionary from user's entered data
        new_routine = {
            "routine_name": routine_name,
            "exercise_one": request.form.get("exercise_one"),
            "exercise_one_reps": int(request.form.get("exercise_one_reps")),
            "exercise_two": request.form.get("exercise_two"),
            "exercise_two_reps": int(request.form.get("exercise_two_reps")),
            "exercise_three": request.form.get("exercise_three"),
            "exercise_three_reps": int(
                                    request.form.get("exercise_three_reps")),
            "username": session["user"]
        }

        # insert new routine dictionary to database and redirect user to
        # my_routines page
        mongo.db.routines.insert_one(new_routine)
        flash("New routine successfully added.")
        return redirect(url_for("my_routines"))

    return render_template("add_routine.html", page_title="Add Routine")


@app.route("/edit_routine/<routine_id>", methods=["GET", "POST"])
@login_required
def edit_routine(routine_id):
    """
    GET: Renders edit_routine page with data from requested routine id
    POST: If current user did not create the requested routine or if the
    submitted routine name is the same as any admin routines or other routines
    by the current user, the user is redirected to the my_routines page.
    Otherwise, the requested routine is updated with the submitted details.
    """
    if request.method == "POST":
        # find routine to edit from database
        routine = mongo.db.routines.find_one({"_id": ObjectId(routine_id)})

        # check current user is the user who created the routine
        if routine["username"] == session["user"]:
            # assign the submitted routine name to a variable
            routine_name = request.form.get("routine_name")

            # check if the submitted routine name has changed
            if routine_name != routine["routine_name"]:
                # check if the current user or admin already has a routine with
                # the requested name
                duplicate_routine = mongo.db.routines.find_one(
                    {
                        "$or": [
                            {
                                "username": session["user"],
                                "routine_name": routine_name
                            },
                            {
                                "username": "admin",
                                "routine_name": routine_name
                            }
                        ]
                    })

                # if a matching routine is found, redirect back to edit
                # routine page
                if duplicate_routine:
                    flash(
                        "Duplicate routine name. Please enter a unique routine"
                        " name.")
                    return redirect(url_for(
                        "edit_routine", routine_id=routine_id))

            # build dictionary containing sumitted routine details
            entry = {
                "routine_name": routine_name,
                "exercise_one": request.form.get("exercise_one"),
                "exercise_one_reps": int(request.form.get(
                                        "exercise_one_reps")),
                "exercise_two": request.form.get("exercise_two"),
                "exercise_two_reps": int(request.form.get(
                                        "exercise_two_reps")),
                "exercise_three": request.form.get("exercise_three"),
                "exercise_three_reps": int(request.form.get(
                                        "exercise_three_reps")),
                "username": session["user"]
            }
            flash("Routine updated.")
            # update the database entry with the entered details
            mongo.db.routines.update_one(routine, {"$set": entry})
            return redirect(url_for("my_routines"))

        # redirect unauthorised users to workout log page
        flash("You don't have permission to edit this routine.")
        return redirect(url_for("my_routines"))

    # find routine to edit from database
    routine = mongo.db.routines.find_one({"_id": ObjectId(routine_id)})
    return render_template(
        "edit_routine.html", page_title="Edit Routine", routine=routine)


@app.route("/delete_routine/<routine_id>")
@login_required
def delete_routine(routine_id):
    """
    Deletes the requested routine and all logs using that routine from the
    database, then redirects the user to the my_routines page
    """
    # find the requested routine in the database and assign it to a variable
    routine = mongo.db.routines.find_one({"_id": ObjectId(routine_id)})

    # check current user is the user who created the routine
    if routine["username"] == session["user"]:
        # find all workout logs matching the given routine _id and delete
        mongo.db.workout_logs.delete_many({"routine_id": ObjectId(routine_id)})

        # delete the routine and redirect user to my_routines page
        mongo.db.routines.delete_one(routine)
        flash("Routine and workout logs deleted.")
        return redirect(url_for("my_routines"))


@app.route("/track_progress/<username>/<routine_id>")
@login_required
def track_progress(username, routine_id):
    """
    If the given user has recorded workouts with the given routine, collect
    data from the database and pass it to the track_progress page template.
    If the user hasn't recorded any data for this routine, redirects to the
    my_routines page.
    """
    # query the database for records matching both the username and routine_id
    # provided, then convert results to a list
    logs = list(mongo.db.workout_logs.find({"$and": [{"username": username},
                                            {"routine_id": ObjectId(routine_id)
                                             }]}).sort("date"))

    # if results were found
    if len(logs) > 0:
        # declare lists to store chart labels and values
        labels = []
        values = []
        # iterate through list of workout logs and append dates to labels list
        # and sets to values list
        for log in logs:
            labels.append(log["date"])
            values.append(log["sets"])

        # assign the record with the highest number of sets to a variable.
        # based on this post from StackOverflow:
        # https://stackoverflow.com/questions/32076382/mongodb-how-to-get-max-value-from-collections
        best = max(logs, key=lambda x: x['sets'])

        # query the database to find the applicable routine and assign to a
        # variable
        routine = mongo.db.routines.find_one({"_id": ObjectId(routine_id)})

        # pass labels, values, personal best and routine data to track_progress
        # template
        return render_template("track_progress.html", labels=labels,
                               values=values, best=best, routine=routine,
                               page_title="Track Progress")

    # if no results found, redirect user to my_routines page
    flash("No workouts recorded with this routine.")
    return redirect(url_for("my_routines"))


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
