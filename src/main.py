from datetime import datetime, timedelta
from binance.spot import Spot
import numpy as np
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json
from dotenv import load_dotenv
import os
from flask_assets import Environment, Bundle
from babel.numbers import format_currency

load_dotenv()

def is_btc_over_120sma():
  client = Spot()
  candles = client.klines(symbol="BTCUSDT", interval="1d", limit=120)
  candles = np.array(candles)[:, 4].astype(np.float64)

  current = candles[-1]
  sma120 = np.mean(candles)
  print(f"current: {current}, sma120: {sma120}")
  
  return candles[-1] > sma120


def fetch_coins(params={}):
  url = f"https://{os.getenv('CMC_API_BASE_URL')}/v1/cryptocurrency/listings/latest"
  parameters = {
    'start':'1',
    'limit':'20',
    'convert':'USD',
    'sort': "volume_24h",
    "sort_dir": "desc",
    "cryptocurrency_type": "coins",
  }
  parameters.update(params)

  print(parameters)

  headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': os.getenv('CMC_API_KEY'),
  }

  session = Session()
  session.headers.update(headers)

  try:
    response = session.get(url, params=parameters)
    print(response.text)
    data = json.loads(response.text)
    return data['data']
          
  except (ConnectionError, Timeout, TooManyRedirects) as e:
    print(e)

def get_momentum_coins():
  print("get_momentum_coins")

  coins = fetch_coins()
  for coin in coins:
    print(f"{coin['symbol']} - {coin['quote']['USD']['volume_24h']}")
  min_volume = coins[-1]['quote']['USD']['volume_24h']
  print(f"min_volume: {min_volume}")

  coins = fetch_coins({'volume_24h_min': min_volume, 'limit': 5, 'sort': 'percent_change_7d'})
  # for coin in coins:
  #   print(f"{coin['name']} {coin['symbol']} {coin['quote']['USD']['percent_change_7d']} {coin['quote']['USD']['volume_24h']}")

  coins = list(map(lambda coin: {'symbol': coin['symbol'], '7d_%': coin['quote']['USD']['percent_change_7d'], 'volume_24h': coin['quote']['USD']['volume_24h']}, coins))
  for coin in coins:
    print(f"{coin['symbol']} {coin['7d_%']} {coin['volume_24h']}")
  return coins


from flask import Flask, render_template
app = Flask(__name__)

assets = Environment(app)

# create bundle for Flask-Assets to compile and prefix scss to css
css = Bundle('styles/main.scss',
             filters=['libsass'],
             output='dist/styles/main.css',
             depends='styles/*.scss')

assets.register("asset_css", css)
css.build()

@app.route('/')
def coins():
    coins = []
    btc_over_120sma = is_btc_over_120sma()
    canInvest = btc_over_120sma
    if canInvest:
      try:
        with open('cache.json') as f:
          cache = json.load(f)
          expired_date = datetime.strptime(cache['fetched_date'], "%Y-%m-%d %H:%M:%S.%f") + timedelta(days=1)
          print(f"expired date: {expired_date}")
          
          coins = cache['coins'] if expired_date > datetime.now() else get_momentum_coins()
      except Exception:
        coins = get_momentum_coins()
        fetched_date = datetime.now()
        with open('cache.json', 'w') as f:
          json.dump({'fetched_date': fetched_date.strftime('%Y-%m-%d %H:%M:%S.%f'), 'coins': coins}, f)

    return render_template('main.html', btcOver120SMA=btc_over_120sma, canInvest=canInvest, coins=coins)

@app.template_filter()
def usd(value):
   return format_currency(value, 'USD', locale='en_US')

app.jinja_env.filters['usd'] = usd

if __name__ == '__main__':
  app.run(host=os.getenv('HOST'), debug=True)

