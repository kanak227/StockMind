import yfinance as yf
import ta 

def check_price_alert(ticker, target_price, direction="above"):
    data = yf.Ticker(ticker).history(period="1d")
    current_price = data["Close"].iloc[-1]
    if direction == "above" and current_price >= target_price:
        return True
    elif direction == "below" and current_price <= target_price:
        return True
    return False

def check_rsi_alert(ticker, threshold=30, direction="below"):
    df = yf.download(ticker, period="21d")
    rsi = ta.momentum.RSIIndicator(df["Close"]).rsi().iloc[-1]
    if direction == "below":
        return rsi < threshold
    else:
        return rsi > threshold
