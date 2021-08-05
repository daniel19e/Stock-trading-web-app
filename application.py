import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

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

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("""
    SELECT symbol, SUM(shares) AS total
    FROM transactions
    WHERE user_id = ?
    GROUP BY symbol
    HAVING total > 0;
    """, session["user_id"])
    cash_row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    table = []
    cash_total = 0
    for row in rows:
        stock = lookup(row["symbol"])
        table.append({
            "symbol": stock["symbol"],
            "name": stock["name"],
            "shares": row["total"],
            "price": usd(stock["price"]),
            "total": usd(row["total"] * stock["price"])
        })
        cash_total += stock["price"] * row["total"]
    cash = cash_row[0]["cash"]
    cash_total += cash

    return render_template("index.html", table=table, cash=usd(cash), cash_total=usd(cash_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        stock_symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        stock = lookup(stock_symbol)

        if not request.form.get("symbol"):
            return apology("must provide a stock symbol", 403)
        if not request.form.get("shares"):
            return apology("must provide number of shares", 403)
        elif not request.form.get("shares").isdigit():
            return apology("invalid number of shares")
        if not stock:
            return apology("invalid stock symbol", 400)
        db_rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        initial_cash = db_rows[0]["cash"]
        current_cash = initial_cash - int(shares) * stock["price"]
        if current_cash < 0:
            return apology("cannot afford")
        db.execute("UPDATE users SET cash=? WHERE id=?", current_cash, session["user_id"])
        db.execute("""
            INSERT INTO transactions (user_id, symbol, shares, price)
            VALUES (?, ?, ?, ?)""", session["user_id"], stock["symbol"], shares, stock["price"])
        flash("Transaction completed successfully!")
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide a stock symbol", 400)
        stock_symbol = request.form.get("symbol").upper()
        stock = lookup(stock_symbol)
        if not stock:
            return apology("invalid stock symbol", 400)
        stock_data={
                'name': stock['name'],
                'symbol': stock['symbol'],
                'price': usd(stock['price'])
            }
        return render_template("quoted.html", stock_data=stock_data)

    if request.method == "GET":
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        hashed_password = generate_password_hash(request.form.get("password"))
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords must match", 400)
        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hashed_password)
            return redirect("/login")
        except:
            return apology("username already exists", 400)

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
