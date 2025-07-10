-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL,
    cash REAL NOT NULL DEFAULT 10000.00
);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    symbol TEXT,
    shares INTEGER,
    price REAL,
    type TEXT NOT NULL, -- 'BUY' or 'SELL'
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Cash history table
CREATE TABLE IF NOT EXISTS cash_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Shorts table
CREATE TABLE IF NOT EXISTS shorts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    shares INTEGER NOT NULL,
    price REAL NOT NULL,
    open_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    close_date TIMESTAMP,
    closed INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Options table
CREATE TABLE IF NOT EXISTS options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    type TEXT NOT NULL, -- 'CALL' or 'PUT'
    strike REAL NOT NULL,
    premium REAL NOT NULL,
    expiration DATE NOT NULL,
    contracts INTEGER NOT NULL,
    open_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
