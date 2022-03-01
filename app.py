import os
from flask import (
    Flask, flash, render_template, 
    redirect, request, session, url_for)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


@app.route("/")
def home():
    """
    Returns the home page for users who aren't logged in.
    """
    return render_template("home.html", page_title="Home")


@app.route("/login")
def login():
    """
    Returns the login page.
    """
    return render_template("login.html", page_title="Login")


@app.route("/register")
def register():
    """
    Returns the registration page.
    """
    return render_template("register.html", page_title="Register")


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
