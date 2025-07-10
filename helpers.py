import csv
import datetime
import pytz
import requests
import subprocess
import urllib
import uuid

from flask import Flask, redirect, render_template, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


ALPHA_VANTAGE_API_KEY = "IWXMTPT7YBSEP5QJ"  # User's provided API key

def lookup(symbol):
    symbol = symbol.upper()
    try:
        # Get current quote
        url = (
            f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={urllib.parse.quote_plus(symbol)}&apikey={ALPHA_VANTAGE_API_KEY}"
        )
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        quote = data.get("Global Quote", {})
        if not quote or not quote.get("05. price"):
            return None
        price = round(float(quote["05. price"]), 2)
        open_price = float(quote.get("02. open", 0))
        high = float(quote.get("03. high", 0))
        low = float(quote.get("04. low", 0))
        volume = int(quote.get("06. volume", 0))
        prev_close = float(quote.get("08. previous close", 0))
        # Try to get daily time series for chart and 52-week range
        url2 = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={urllib.parse.quote_plus(symbol)}&interval=1min&apikey={ALPHA_VANTAGE_API_KEY}&outputsize=compact"
        try:
            response2 = requests.get(url2)
            response2.raise_for_status()
            data2 = response2.json()
            timeseries = data2.get("Time Series (1min)", {})
            if timeseries:
                dates = sorted(timeseries.keys(), reverse=True)
                closes = [float(timeseries[date]["4. close"]) for date in dates]
                chart_dates = dates[:30][::-1]
                chart_closes = closes[:30][::-1]
            else:
                chart_dates = chart_closes = None
        except Exception:
            chart_dates = chart_closes = None
        # For 52-week range, fallback to daily adjusted
        week52_high = week52_low = None
        try:
            url3 = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={urllib.parse.quote_plus(symbol)}&apikey={ALPHA_VANTAGE_API_KEY}&outputsize=full"
            response3 = requests.get(url3)
            response3.raise_for_status()
            data3 = response3.json()
            ts_daily = data3.get("Time Series (Daily)", {})
            if ts_daily:
                dkeys = sorted(ts_daily.keys(), reverse=True)
                dcloses = [float(ts_daily[date]["4. close"]) for date in dkeys]
                closes_365 = dcloses[:min(365, len(dcloses))]
                week52_high = max(closes_365) if closes_365 else high
                week52_low = min(closes_365) if closes_365 else low
        except Exception:
            pass
        return {
            "name": symbol,
            "price": price,
            "symbol": symbol,
            "open": open_price,
            "high": high,
            "low": low,
            "volume": volume,
            "prev_close": prev_close,
            "week52_high": week52_high,
            "week52_low": week52_low,
            "chart_dates": chart_dates,
            "chart_closes": chart_closes
        }
    except Exception as e:
        print(f"Lookup error: {e}")
        return None


def usd(value):
    """Format value as USD."""
    if value is None or value == "" or (isinstance(value, float) and (value != value)):
        return "$0.00"
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"

# Register usd filter globally for Jinja2
from flask import current_app
try:
    import flask
    if flask.has_app_context():
        current_app.jinja_env.filters['usd'] = usd
except Exception:
    pass

def add_template_filters(app: Flask):
    app.jinja_env.filters['usd'] = usd


def is_market_open():
    now = datetime.datetime.now(pytz.timezone("US/Eastern"))
    # Market open: 9:30am, close: 4:00pm, Mon-Fri
    if now.weekday() >= 5:
        return False
    open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_time <= now <= close_time
