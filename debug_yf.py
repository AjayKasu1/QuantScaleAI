import yfinance as yf
tickers = ["AAPL", "MSFT"]
data = yf.download(tickers, start="2024-01-01", progress=False)
print("Columns:", data.columns)
try:
    print(data['Adj Close'].head())
except Exception as e:
    print("Error accessing Adj Close:", e)
    print(data.head())
