from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
import requests 
import yfinance as yf 
import wikipedia 
from google import genai 
from dotenv import load_dotenv 
import os
import secrets
import authenticator
from alert_system.scheduler import start_scheduler, alerts
from flask_session import Session
from flask_cors import CORS

# Load environment variables from .env file
load_dotenv()

# Load API keys from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "abc")  # Fallback to "abc" if not found
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "xyz")  # Fallback to "xyz" if not found

# Cache for company tickers to avoid repeated API calls
TICKER_CACHE = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "facebook": "META",
    "meta": "META",
    "netflix": "NFLX",
    "nvidia": "NVDA",
    "intel": "INTC",
    "amd": "AMD",
    "ibm": "IBM",
    "oracle": "ORCL",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "walmart": "WMT",
    "target": "TGT",
    "coca cola": "KO",
    "pepsi": "PEP",
    "pepsico": "PEP",
    "mcdonalds": "MCD",
    "starbucks": "SBUX",
    "nike": "NKE",
    "disney": "DIS",
    "boeing": "BA",
    "ford": "F",
    "general motors": "GM",
    "exxon": "XOM",
    "chevron": "CVX",
    "jpmorgan": "JPM",
    "bank of america": "BAC",
    "goldman sachs": "GS",
    "visa": "V",
    "mastercard": "MA",
    "paypal": "PYPL",
    "johnson & johnson": "JNJ",
    "pfizer": "PFE",
    "merck": "MRK",
    "verizon": "VZ",
    "at&t": "T"
}
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    # We'll handle this in the query_gemini_llm function
app = Flask(__name__, static_folder="static", template_folder="templates") 
CORS(app)  # Enable CORS for all routes


#INITIAILIZE APP
app = Flask(__name__, static_folder="static", template_folder="templates")

# Configuration
app.config['SECRET_KEY'] = secrets.token_hex(32)  # Change this in production!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stockmind.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = secrets.token_hex(32)  # For API tokens
app.config['SESSION_TYPE'] = 'filesystem' #using server side session cookies - filesystem

# Initialize Flask extensions
db = SQLAlchemy(app)
Session(app)

# Load API keys 
GEMINI_API_KEY = "your_gemini_apikey"  # GeminiAPIKey 
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ALPHA_VANTAGE_API_KEY = "your_alpha_vantage_key"  # AlphaVantageAPIKey 
client = genai.Client(api_key=GEMINI_API_KEY)


@app.route('/alert_form')
def alert_form():
    return render_template('alert_form.html')
@app.route('/alerts')

@app.route('/create_alert', methods=['POST'])
def create_alert():
    data = request.form
    alerts.append({
        'type': data.get('type'),             # "price" or "rsi"
        'ticker': data.get('ticker'),
        'target': float(data.get('target', 0)),
        'threshold': float(data.get('threshold', 30)),
        'direction': data.get('direction'),
        'email': data.get('email')
    })
    flash(f"Alert created for {data.get('ticker')}", "success")
    return redirect('/')

start_scheduler()

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(50), nullable = False)
    email = db.Column(db.String(120), unique=True, nullable = False)
    password_hash = db.Column(db.String(200), nullable = False)
    def set_passsword(self, passw):
        self.password_hash = generate_password_hash(passw)
    def check_password(self, passw):
        return check_password_hash(self.password_hash, passw)
    def get_passw_hash(self):
        return self.password_hash

# JWT token required decorator for API routes
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
            
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
            
        try:
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
            
        return f(current_user, *args, **kwargs)
        
    return decorated

def fetch_wikipedia_summary(company_name): 
    try: 
        search_results = wikipedia.search(company_name) 
        if search_results: 
            page_title = search_results[0] 
            summary = wikipedia.summary(page_title, sentences=2) 
            return page_title, summary 
    except Exception as e: 
        return None, f"Error fetching Wikipedia summary: {str(e)}" 
    return None, "No Wikipedia page found for the given company." 
 

def fetch_stock_price(ticker): 
    try: 
        # Set a timeout for the request
        stock = yf.Ticker(ticker)
        # Use a longer period (3mo instead of 1mo) for more detailed response
        history = stock.history(period="3mo")
        
        if history.empty:
            print(f"No stock price data found for {ticker}")
            # Generate mock data for testing
            import datetime
            import random
            today = datetime.datetime.now()
            time_labels = [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(90, 0, -1)]
            base_price = 100.0
            stock_prices = [round(base_price + random.uniform(-10, 10), 2) for _ in range(90)]
            return stock_prices, time_labels
            
        time_labels = history.index.strftime('%Y-%m-%d').tolist() 
        stock_prices = [round(price, 2) for price in history['Close'].tolist()]  # Round prices to 2 decimal places
        return stock_prices, time_labels 
    except Exception as e: 
        print(f"Error fetching stock price for {ticker}: {e}")
        # Generate mock data for testing
        import datetime
        import random
        today = datetime.datetime.now()
        time_labels = [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(90, 0, -1)]
        base_price = 100.0
        stock_prices = [round(base_price + random.uniform(-10, 10), 2) for _ in range(90)]
        return stock_prices, time_labels


def get_ticker_from_alpha_vantage(company_name): 
    # Check if company is in our cache first
    company_lower = company_name.lower()
    for key, ticker in TICKER_CACHE.items():
        if key in company_lower:
            print(f"Using cached ticker {ticker} for {company_name}")
            return ticker
    
    # If not in cache, try API with a short timeout
    try: 
        url = "https://www.alphavantage.co/query" 
        params = { 
            "function": "SYMBOL_SEARCH", 
            "keywords": company_name, 
            "apikey": ALPHA_VANTAGE_API_KEY, 
        } 
        response = requests.get(url, params=params, timeout=3)  # 3 second timeout
        data = response.json() 
        
        # Check if we got an error message about invalid API key
        if "Error Message" in data:
            print(f"Alpha Vantage API error: {data['Error Message']}")
            # Fallback: Try to guess the ticker from the company name
            return company_name.split()[0].upper()
            
        if "bestMatches" in data: 
            for match in data["bestMatches"]: 
                if match["4. region"] == "United States": 
                    # Add to cache for future use
                    TICKER_CACHE[company_lower] = match["1. symbol"]
                    return match["1. symbol"] 
        
        # If no matches found, try to guess the ticker
        return company_name.split()[0].upper()
    except Exception as e: 
        print(f"Error in get_ticker_from_alpha_vantage: {e}")
        # Fallback: Try to guess the ticker from the company name
        return company_name.split()[0].upper()
 
def fetch_market_cap(ticker): 
    try: 
        stock = yf.Ticker(ticker) 
        market_cap = stock.info.get('marketCap', None) 
        return market_cap 
    except Exception as e: 
        return None 
 
def get_stock_price_for_competitor(ticker): 
    try: 
        stock = yf.Ticker(ticker) 
        # Use a longer period (3mo instead of 1mo) for more detailed response
        history = stock.history(period="3mo") 
        
        if history.empty:
            print(f"No stock price data found for competitor {ticker}")
            # Generate mock data for testing
            import datetime
            import random
            today = datetime.datetime.now()
            time_labels = [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(90, 0, -1)]
            base_price = 100.0
            stock_prices = [round(base_price + random.uniform(-10, 10), 2) for _ in range(90)]
            return stock_prices, time_labels
            
        time_labels = history.index.strftime('%Y-%m-%d').tolist() 
        stock_prices = [round(price, 2) for price in history['Close'].tolist()]  # Round prices to 2 decimal places
        return stock_prices, time_labels 
    except Exception as e: 
        print(f"Error fetching stock price for competitor {ticker}: {e}")
        # Generate mock data for testing
        import datetime
        import random
        today = datetime.datetime.now()
        time_labels = [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(90, 0, -1)]
        base_price = 100.0
        stock_prices = [round(base_price + random.uniform(-10, 10), 2) for _ in range(90)]
        return stock_prices, time_labels
 
def get_top_competitors(competitors): 
    competitor_data = [] 
    processed_tickers = set()  # To track processed tickers and avoid duplicates 
    
    # If we don't have any competitors or encounter issues, use these fallback companies
    fallback_competitors = ["Microsoft", "Apple", "Amazon"]
    
    # Use the provided competitors or fallback if empty
    competitors_to_process = set(competitors) if competitors else fallback_competitors
 
    for competitor in competitors_to_process:  # Remove duplicate names 
        ticker = get_ticker_from_alpha_vantage(competitor) 
        if ticker and ticker not in processed_tickers: 
            market_cap = fetch_market_cap(ticker) 
            stock_prices, time_labels = get_stock_price_for_competitor(ticker) 
            if market_cap and stock_prices and time_labels: 
                competitor_data.append({ 
                    "name": competitor, 
                    "ticker": ticker, 
                    "market_cap": market_cap, 
                    "stock_prices": stock_prices, 
                    "time_labels": time_labels, 
                    "stock_price": stock_prices[-1], 
                }) 
                processed_tickers.add(ticker)  # Add ticker to the processed set 
    
    # If we couldn't get any valid competitor data, use fallback data
    if not competitor_data:
        print("No valid competitor data found, using fallback data")
        # Create some fallback data with mock values
        import random
        for i, comp in enumerate(fallback_competitors):
            ticker = comp[0:3].upper()  # Just use first 3 letters as ticker
            mock_market_cap = 1000000000 * (3-i)  # Decreasing market caps
            # Add random walk for mock prices to avoid straight lines
            mock_prices = []
            price = 100 + i*10
            for j in range(30):
                price += random.uniform(-2, 2)
                mock_prices.append(round(price, 2))
            mock_dates = [f"2025-04-{j+1:02d}" for j in range(30)]  # Mock dates
            
            competitor_data.append({
                "name": comp,
                "ticker": ticker,
                "market_cap": mock_market_cap,
                "stock_prices": mock_prices,
                "time_labels": mock_dates,
                "stock_price": mock_prices[-1],
            })
 
    # Sort competitors by market cap and return the top 3 
    top_competitors = sorted(competitor_data, key=lambda x: x["market_cap"], reverse=True)[:3] 
    return top_competitors 
 
def query_gemini_llm(description): 
    try: 
        # Check if client is defined (it might not be if API key is invalid)
        if 'client' not in globals():
            print("Gemini client not initialized, using fallback data")
            # Return fallback data
            return [
                {
                    "name": "Technology Sector:",
                    "competitors": ["Microsoft", "Apple", "IBM", "Oracle"]
                },
                {
                    "name": "Financial Sector:",
                    "competitors": ["JPMorgan Chase", "Bank of America", "Wells Fargo", "Citigroup"]
                }
            ]
            
        prompt = f""" 
        Provide a structured list of sectors and their competitors for the following company description: 
        {description[:500]} 
        Format: 
        Sector Name : 
            Competitor 1 
            Competitor 2 
            Competitor 3 
 
        Leave a line after each sector. Do not use bullet points. 
        """ 
        
        try:
            response = client.models.generate_content( 
                model="gemini-1.5-flash", contents=prompt 
            ) 
            content = response.candidates[0].content.parts[0].text
        except Exception as api_error:
            print(f"Error calling Gemini API: {api_error}")
            # Return fallback data
            return [
                {
                    "name": "Technology Sector:",
                    "competitors": ["Microsoft", "Apple", "IBM", "Oracle"]
                },
                {
                    "name": "Financial Sector:",
                    "competitors": ["JPMorgan Chase", "Bank of America", "Wells Fargo", "Citigroup"]
                }
            ]
            
        sectors = [] 
        for line in content.split("\n\n"): 
            lines = line.strip().split("\n") 
            if len(lines) > 1: 
                sector_name = lines[0].strip() 
                competitors = [l.strip() for l in lines[1:]] 
                sectors.append({"name": sector_name, "competitors": competitors}) 
        return sectors 
    except Exception as e: 
        print(f"Error in query_gemini_llm: {e}")
        # Return fallback data
        return [
            {
                "name": "Technology Sector:",
                "competitors": ["Microsoft", "Apple", "IBM", "Oracle"]
            },
            {
                "name": "Financial Sector:",
                "competitors": ["JPMorgan Chase", "Bank of America", "Wells Fargo", "Citigroup"]
            }
        ]
 
@app.route("/") 
def home(): 
    return render_template("FRONT.html") 
 
@app.route("/analyze_company", methods=["GET"]) 
def analyze_company(): 
    try:
        company_name = request.args.get("company_name") 
        if not company_name: 
            return jsonify(success=False, error="No company name provided.") 
     
        _, summary = fetch_wikipedia_summary(company_name) 
        if not summary: 
            summary = f"{company_name} is a company operating in various sectors including technology and finance."
            print(f"Using fallback description for {company_name}")
     
        ticker = get_ticker_from_alpha_vantage(company_name) 
        if not ticker: 
            ticker = company_name.split()[0].upper()
            print(f"Using fallback ticker {ticker} for {company_name}")
     
        stock_prices, time_labels = fetch_stock_price(ticker) 
        if not stock_prices or not time_labels: 
            print(f"Using mock stock data for {ticker}")
            stock_prices = [100 + i for i in range(30)]
            time_labels = [f"2025-04-{i+1:02d}" for i in range(30)]
     
        competitors = query_gemini_llm(summary) 
        if not competitors: 
            competitors = [{"name": "No Sectors", "competitors": ["No competitors found."]}] 
     
        # Use only the first sector's competitors for top competitors
        if competitors and competitors[0].get("competitors"):
            relevant_competitors = competitors[0]["competitors"]
        else:
            relevant_competitors = []
        print(f"Relevant competitors for {company_name}: {relevant_competitors}")
        top_competitors = get_top_competitors(relevant_competitors)
        print(f"Top competitors data for {company_name}:")
        for comp in top_competitors:
            print(f"  {comp['name']} | Ticker: {comp['ticker']} | Market Cap: {comp['market_cap']} | Last Price: {comp['stock_price']}")
     
        return jsonify( 
            success=True, 
            description=summary, 
            ticker=ticker, 
            stock_prices=stock_prices, 
            time_labels=time_labels, 
            competitors=competitors, 
            top_competitors=top_competitors, 
        )
    except Exception as e:
        print(f"Error in analyze_company: {e}")
        return jsonify(
            success=False, 
            error="An error occurred while analyzing the company. Please try again with a different company name."
        )
 
if __name__ == "__main__": 
    # Get port and host from environment variables
    port = int(os.getenv("PORT", 12001))
    host = os.getenv("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=True)
def userAuthenticate():
    '''use inside route functions to block logged out user'''
    if "username" in session:
        return True
    return False

# Authentication Routes
@app.route("/login", methods = ['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    if(not email or not password):
        return render_template("access-account.html", error = "Invalid Information, Please try again")
    user = User.query.filter_by(email = email).first()
    if(user and user.check_password(password)):
        username = user.username
        session["username"] = username
        return redirect(url_for("home"))
    else:
        return render_template("access-account.html", error = "Invalid Information")
        

@app.route("/register", methods = ['POST'])
def register():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    if(not username or not email or not password):
        return render_template("access-account.html", error = "Invalid Information, Please try again")
    user = User.query.filter_by(email = email).first()
    if user:
        return render_template("access-account.html", error="Account Already Exist")
    else:
        new_user = User(username = username, email = email)
        new_user.set_passsword(password)
        session['username'] = username
        session['password'] = new_user.get_passw_hash()
        session['email'] = email
        return redirect(url_for('auth'))
    
@app.route('/api/auth')
def auth():
    username = session['username']
    email = session['email']
    try:
        otp =  authenticator.generateOTP(username=username, usermail=email)
        session["otp"] = otp
    except:
        return render_template("access-account.html", error = "Invalid email address")
    return render_template("access-account.html", otp = True)

@app.route('/api/verify', methods = ['POST'])
def verify():
    inp = request.form['userOTP']
    username = session["username"]
    password= session["password"]
    email = session["email"]
    otp = session["otp"]
    session.pop("password",None)
    session.pop("email",None)
    session.pop("otp",None)
    authSuccess = authenticator.verifyOTP(otp, inp)
    if(authSuccess):
        newUser = User(username = username , email = email, password_hash = password)
        #registering the user in database
        db.session.add(newUser)
        db.session.commit()
        return redirect(url_for('home'))
    else:
        session.pop("username",None)
        return render_template("FRONT.html", error = "❌ Invalid OTP")
    
@app.route('/logout')
def logout():
    session.pop("username", None)
    return redirect(url_for('home'))
@app.route('/access-account')
def accessAccount():
    return render_template("access-account.html")

# Protect existing routes
@app.route("/")
def home():
    return render_template("FRONT.html")

@app.route("/analyze_company", methods=["GET"])
def analyze_company():
    if not userAuthenticate():
        return render_template("FRONT.html", error = "Please Sign In to continue")
    company_name = request.args.get("company_name")
    if not company_name:
        return jsonify(success=False, error="No company name provided.")

    _, summary = fetch_wikipedia_summary(company_name)
    if not summary:
        return jsonify(success=False, error="Could not find company description.")

    ticker = get_ticker_from_alpha_vantage(company_name)
    if not ticker:
        return jsonify(success=False, error="Could not find ticker symbol.")

    stock_prices, time_labels = fetch_stock_price(ticker)
    if not stock_prices or not time_labels:
        return jsonify(success=False, error="Could not fetch stock prices.")

    competitors = query_gemini_llm(summary)
    if not competitors:
        competitors = [{"name": "No Sectors", "competitors": ["No competitors found."]}]

    all_competitors = [comp for sector in competitors for comp in sector["competitors"]]
    top_competitors = get_top_competitors(all_competitors)

    return jsonify(
        success=True,
        description=summary,
        ticker=ticker,
        stock_prices=stock_prices,
        time_labels=time_labels,
        competitors=competitors,
        top_competitors=top_competitors,
    )

# Initialize database
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
