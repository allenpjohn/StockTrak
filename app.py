import os
from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
from helpers import apology, login_required, lookup, usd, add_template_filters, is_market_open

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Register template filters
add_template_filters(app)

# Database setup
DATABASE = "stocktrak.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
@login_required
def index():
    db = get_db()
    cur = db.cursor()
    # Get user's cash
    cur.execute("SELECT cash FROM users WHERE id = ?", (session["user_id"],))
    cash = cur.fetchone()["cash"]
    # Get user's stock holdings (aggregate shares), exclude 0 shares
    cur.execute("SELECT symbol, SUM(CASE WHEN type='BUY' THEN shares ELSE -shares END) as shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING shares > 0", (session["user_id"],))
    holdings = cur.fetchall()
    portfolio = []
    total = cash
    for row in holdings:
        symbol = row["symbol"]
        shares = row["shares"]
        quote = lookup(symbol)
        if not quote:
            price = 0
            name = symbol
        else:
            price = quote["price"]
            name = quote["name"]
        total_value = price * shares
        total += total_value
        portfolio.append({
            "symbol": symbol,
            "name": name,
            "shares": shares,
            "price": price,
            "total": total_value
        })
    return render_template("index.html", portfolio=portfolio, cash=cash, total=total)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username or not password or not confirmation:
            return apology("must provide username and password", 400)
        if password != confirmation:
            return apology("passwords do not match", 400)
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            return apology("username already exists", 400)
        hash_pw = generate_password_hash(password)
        cur.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, hash_pw))
        db.commit()
        user_id = cur.lastrowid
        session["user_id"] = user_id
        flash("Registered successfully!")
        return redirect("/")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            return apology("must provide username and password", 400)
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT id, hash FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if row is None or not check_password_hash(row["hash"], password):
            return apology("invalid username and/or password", 400)
        session["user_id"] = row["id"]
        flash("Logged in successfully!")
        return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    quote = None
    error = None
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            error = "Must provide symbol."
        else:
            quote = lookup(symbol)
            if not quote or not quote.get("price"):
                error = f"Invalid symbol: {symbol.upper()}"
                quote = None
    return render_template("quote.html", quote=quote, error=error)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        if not is_market_open():
            return apology("Trading is only allowed during US market hours (9:30am-4:00pm ET, Mon-Fri)")
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol or not shares:
            return apology("must provide symbol and shares", 400)
        try:
            shares = int(shares)
            if shares <= 0:
                raise ValueError
        except ValueError:
            return apology("shares must be a positive integer", 400)
        quote = lookup(symbol)
        if not quote or not quote.get("price"):
            return apology("invalid symbol", 400)
        price = float(quote["price"])
        total_cost = price * shares
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT cash FROM users WHERE id = ?", (session["user_id"],))
        cash = cur.fetchone()["cash"]
        if total_cost > cash:
            return apology("not enough cash", 400)
        # Update cash
        cur.execute("UPDATE users SET cash = cash - ? WHERE id = ?", (total_cost, session["user_id"]))
        # Log transaction
        cur.execute("INSERT INTO transactions (user_id, symbol, shares, price, type) VALUES (?, ?, ?, ?, 'BUY')", (session["user_id"], symbol.upper(), shares, price))
        db.commit()
        flash(f"Bought {shares} shares of {symbol.upper()}!")
        return redirect("/")
    return render_template("buy.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    db = get_db()
    cur = db.cursor()
    if request.method == "POST":
        if not is_market_open():
            return apology("Trading is only allowed during US market hours (9:30am-4:00pm ET, Mon-Fri)")
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol or not shares:
            return apology("must provide symbol and shares", 400)
        try:
            shares = int(shares)
            if shares <= 0:
                raise ValueError
        except ValueError:
            return apology("shares must be a positive integer", 400)
        symbol = symbol.upper()
        # Check user holdings
        cur.execute("SELECT SUM(CASE WHEN type='BUY' THEN shares ELSE -shares END) as shares FROM transactions WHERE user_id = ? AND symbol = ?", (session["user_id"], symbol))
        row = cur.fetchone()
        owned = row["shares"] if row["shares"] else 0
        if shares > owned:
            return apology("not enough shares to sell", 400)
        quote = lookup(symbol)
        if not quote or not quote.get("price"):
            return apology("invalid symbol", 400)
        price = float(quote["price"])
        # Update cash
        cur.execute("UPDATE users SET cash = cash + ? WHERE id = ?", (price * shares, session["user_id"]))
        # Log transaction
        cur.execute("INSERT INTO transactions (user_id, symbol, shares, price, type) VALUES (?, ?, ?, ?, 'SELL')", (session["user_id"], symbol, shares, price))
        db.commit()
        flash(f"Sold {shares} shares of {symbol}!")
        return redirect("/")
    return render_template("sell.html")

@app.route("/history")
@login_required
def history():
    db = get_db()
    cur = db.cursor()
    # Get all history
    cur.execute("SELECT date, type, symbol, shares, price, NULL as cash_change FROM transactions WHERE user_id = ?", (session["user_id"],))
    stock_rows = cur.fetchall()
    cur.execute("SELECT date, 'CASH' as type, NULL as symbol, NULL as shares, NULL as price, amount as cash_change FROM cash_history WHERE user_id = ?", (session["user_id"],))
    cash_rows = cur.fetchall()
    all_rows = [dict(row) for row in stock_rows] + [dict(row) for row in cash_rows]
    all_rows.sort(key=lambda r: r['date'], reverse=True)
    # Pagination
    from flask import request
    page = int(request.args.get('page', 1))
    per_page = 15
    total = len(all_rows)
    max_page = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, max_page))
    start = (page - 1) * per_page
    end = start + per_page
    page_rows = all_rows[start:end]
    return render_template("history.html", history=page_rows, page=page, max_page=max_page)

@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT cash FROM users WHERE id = ?", (session["user_id"],))
    cash_now = cur.fetchone()["cash"]
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount"))
        except (TypeError, ValueError):
            return apology("invalid amount", 400)
        if cash_now + amount < 0:
            return apology("not enough cash to subtract", 400)
        cur.execute("UPDATE users SET cash = cash + ? WHERE id = ?", (amount, session["user_id"]))
        cur.execute("INSERT INTO cash_history (user_id, amount) VALUES (?, ?)", (session["user_id"], amount))
        db.commit()
        flash(f"{'Added' if amount >= 0 else 'Subtracted'} ${abs(amount):,.2f} to your account.")
        return redirect("/cash")
    return render_template("cash.html", cash=cash_now)

@app.route("/short", methods=["GET", "POST"])
@login_required
def short():
    db = get_db()
    cur = db.cursor()
    message = None
    if request.method == "POST":
        action = request.form.get("action")
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol or not shares:
            return apology("must provide symbol and shares", 400)
        try:
            shares = int(shares)
            if shares <= 0:
                raise ValueError
        except ValueError:
            return apology("shares must be a positive integer", 400)
        symbol = symbol.upper()
        quote = lookup(symbol)
        if not quote or not quote.get("price"):
            return apology("invalid symbol", 400)
        price = float(quote["price"])
        if action == "short_sell":
            # Credit user with cash and record short position
            cur.execute("UPDATE users SET cash = cash + ? WHERE id = ?", (price * shares, session["user_id"]))
            cur.execute("INSERT INTO shorts (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", (session["user_id"], symbol, shares, price))
            db.commit()
            message = f"Short sold {shares} shares of {symbol} at {usd(price)}."
        elif action == "short_buy":
            # Find open short position
            cur.execute("SELECT * FROM shorts WHERE user_id = ? AND symbol = ? AND closed = 0 ORDER BY open_date LIMIT 1", (session["user_id"], symbol))
            short_row = cur.fetchone()
            if not short_row or short_row["shares"] < shares:
                return apology("not enough shorted shares to buy back", 400)
            # Deduct cash for buyback
            cur.execute("SELECT cash FROM users WHERE id = ?", (session["user_id"],))
            user_cash = cur.fetchone()["cash"]
            total_cost = price * shares
            if user_cash < total_cost:
                return apology("not enough cash to buy back shares", 400)
            cur.execute("UPDATE users SET cash = cash - ? WHERE id = ?", (total_cost, session["user_id"]))
            # Update or close short position
            if short_row["shares"] == shares:
                cur.execute("UPDATE shorts SET closed = 1, close_date = CURRENT_TIMESTAMP WHERE id = ?", (short_row["id"],))
            else:
                cur.execute("UPDATE shorts SET shares = shares - ? WHERE id = ?", (shares, short_row["id"]))
            db.commit()
            message = f"Bought back {shares} shares of {symbol} at {usd(price)}."
    # Show current open shorts
    cur.execute("SELECT * FROM shorts WHERE user_id = ? AND closed = 0", (session["user_id"],))
    shorts = cur.fetchall()
    return render_template("short.html", shorts=shorts, message=message)

@app.route("/options", methods=["GET", "POST"])
@login_required
def options():
    db = get_db()
    cur = db.cursor()
    message = None
    if request.method == "POST":
        if not is_market_open():
            return apology("Options trading is only allowed during US market hours (9:30am-4:00pm ET, Mon-Fri)")
        symbol = request.form.get("symbol")
        type_ = request.form.get("type")
        strike = request.form.get("strike")
        premium = request.form.get("premium")
        expiration = request.form.get("expiration")
        contracts = request.form.get("contracts")
        if not all([symbol, type_, strike, premium, expiration, contracts]):
            return apology("all fields required", 400)
        if type_ not in ["CALL", "PUT"]:
            return apology("invalid option type", 400)
        try:
            strike = float(strike)
            premium = float(premium)
            contracts = int(contracts)
            if strike <= 0 or premium < 0 or contracts <= 0:
                raise ValueError
        except ValueError:
            return apology("invalid strike, premium, or contracts", 400)
        # Log the option position
        cur.execute("INSERT INTO options (user_id, symbol, type, strike, premium, expiration, contracts) VALUES (?, ?, ?, ?, ?, ?, ?)", (session["user_id"], symbol.upper(), type_, strike, premium, expiration, contracts))
        db.commit()
        message = f"Bought {contracts} {type_} option(s) for {symbol.upper()} at strike {usd(strike)} (premium {usd(premium)}) expiring {expiration}"
    # Show current open options
    cur.execute("SELECT * FROM options WHERE user_id = ? AND closed = 0", (session["user_id"],))
    options = cur.fetchall()
    return render_template("options.html", options=options, message=message)

if __name__ == "__main__":
    app.run(debug=True)
