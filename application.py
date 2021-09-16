import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    users = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])

    stocks = db.execute(
        "SELECT name, SUM(number) as total_shares, SUM(value) as totalcost FROM portfolio WHERE userId = :id GROUP BY name HAVING total_shares > 0", id=session["user_id"])

    quotes = {}

    total = 0
    for stock in stocks:
        quotes[stock["name"]] = lookup(stock["name"])
        total = total + stock["totalcost"]

    cash_remaining = users[0]["cash"]

    return render_template("index.html", quotes=quotes, stocks=stocks, total=total, cash_remaining=cash_remaining)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Missing Symbol", 400)

        if not request.form.get("shares"):
            return apology("Missing Number of Shares", 400)

        # Check if shares was a positive integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Shares must be a positive integer", 400)

        # Check if # of shares requested was 0
        if shares <= 0:
            return apology("Can't buy less than or 0 shares", 400)

        quote = lookup(request.form.get("symbol"))

        if quote == None:
            return apology("Invalid Quote", 400)

        rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        # Ensure username exists and password is correct
        if len(rows) != 1:
            return apology("invalid username and/or password", 400)

        buyValue = quote["price"] * float(request.form.get("shares"))

        # Check if he has sufficent cash to buy
        if rows[0]["cash"] < buyValue:
            return apology("Insuffici#ent cash", 400)

        cashRemaining = rows[0]["cash"] - buyValue

        # Make an entry in the portfolio table
        result = db.execute("INSERT INTO portfolio (userId, name, price, number, value) VALUES (:userid, :symbol, :price, :shares, :value)",
                            userid=session["user_id"], symbol=quote["symbol"], price=quote["price"], shares=int(request.form.get("shares")), value=buyValue)

        # Ensure username exists and password is correct
        if not result:
            return apology("Unable to update portfolio", 400)

        # Update the cash for the user
        result = db.execute("UPDATE users SET cash = :left WHERE id = :id", id=session["user_id"], left=cashRemaining)

        # Redirect user to home page

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history", methods=["GET"])
@login_required
def history():
    """Show history of transactions"""

    if request.method == "GET":
        rows = db.execute("SELECT name, number, value, date FROM portfolio WHERE userId = :id", id=session["user_id"])

        if len(rows) == 0:
            return apology("No history present", 400)

        return render_template("history.html", portfolios=rows)
    else:
        return apology("Invalid option", 400)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/display", methods=["GET"])
@login_required
def display():
    return render_template("display.html", quote)


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Missing Symbol", 400)

        quote = lookup(request.form.get("symbol"))

        if quote == None:
            return apology("Invalid Quote", 400)

        # Redirect user to home page
        return render_template("display.html", quote=quote)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Missing Username!", 400)

        if len(request.form.get("username").strip()) == 0:
            return apology("Username cannot be blank", 400)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("Must provide password", 400)

        if len(request.form.get("password").strip()) == 0:
            return apology("Password cannot be blank", 400)

        # Ensure confirmation password was submitted
        if not request.form.get("confirmation"):
            return apology("must provide confirmation", 400)

        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("confiirmation and password should be the same", 400)

        hash = generate_password_hash(request.form.get("password"))

        # Query database for username
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                            username=request.form.get("username"), hash=hash)

        # Ensure username exists and password is correct
        if not result:
            return apology("Username already exists", 400)

        # Remember which user has logged in
        session["user_id"] = result

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Missing Symbol", 400)

        if not request.form.get("shares"):
            return apology("Missing Number of Shares", 400)

        quote = lookup(request.form.get("symbol"))

        if quote == None:
            return apology("Invalid Symbol", 400)

        stocks = db.execute("SELECT name, SUM(number) as total_shares FROM portfolio WHERE userId = :id AND name= :symbol GROUP BY name HAVING total_shares > 0",
                            id=session["user_id"], symbol=request.form.get("symbol"))
        if not stocks:
            return apology("Shares not found", 400)

        if stocks[0]["total_shares"] < int(request.form.get("shares")):
            return apology("Insufficient shares to sell", 400)

        rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        sellValue = quote["price"] * float(request.form.get("shares"))

        newcashRemaining = rows[0]["cash"] + sellValue

        # Make an entry in the portfolio table
        result = db.execute("INSERT INTO portfolio (userId, name, price, number, value) VALUES (:userid, :symbol, :price, :shares, :value)",
                            userid=session["user_id"], symbol=quote["symbol"], price=quote["price"], shares=-1 * (int(request.form.get("shares"))), value=sellValue * -1)

        # Ensure username exists and password is correct
        if not result:
            return apology("Unable to update portfolio", 400)

        # Update the cash for the user
        result = db.execute("UPDATE users SET cash = :left WHERE id = :id", id=session["user_id"], left=newcashRemaining)

        # Redirect user to home page

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        stocks = db.execute(
            "SELECT name as symbol, SUM(number) as total_shares FROM portfolio WHERE userId = :id GROUP BY name HAVING total_shares > 0", id=session["user_id"])

        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
