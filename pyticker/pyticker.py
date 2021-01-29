import os
import sys
import time
import subprocess

from datetime import datetime

import cursor
import schedule
import bashplotlib
import requests

from termcolor import colored
import ujson as json


def api_call(symbols):
	# endpoint
	endpoint = "https://query1.finance.yahoo.com/v7/finance/quote?lang=en-US&region=US&corsDomain=finance.yahoo.com"

	# symbols to follow
	flds = (
		"symbol", "marketState", "regularMarketPrice", "regularMarketChange",
  		"regularMarketChangePercent", "preMarketPrice", "preMarketChange",
  		"preMarketChangePercent", "postMarketPrice", "postMarketChange",
  		"postMarketChangePercent"
  	)

	# request url
	requrl = f"{endpoint}&fields={','.join(flds)}&symbols={','.join(symbols)}"

	# do request
	API_RESPONSE = requests.get(requrl)
	api_json = json.loads(API_RESPONSE.text)

	symbol_vals['DATA_USAGE'] += len(API_RESPONSE.content)

	print_tickers(tickers=api_json['quoteResponse']['result'])


def print_tickers(tickers):
	tmaxlen = max([len(ticker['symbol']) for ticker in tickers])
	if tmaxlen < len('TICKER'):
		# make sure the header fits
		tmaxlen = len('TICKER')

	pmaxlen = max([len(f"{ticker['regularMarketPrice']:.4f}") for ticker in tickers])
	mstatemaxlen, pchmaxlen = 0, 0

	printstr = ''
	for ticker in tickers:
		symbol = ticker['symbol']
		mstate = ticker['marketState']

		if mstate in ('REGULAR', 'POSTPOST', 'PREPRE', 'CLOSED'):
			price = ticker['regularMarketPrice']
			pchange = ticker['regularMarketChangePercent']
		elif mstate == 'PRE':
			try:
				price = ticker['preMarketPrice']
				pchange = ticker['preMarketChangePercent']
			except:
				price = ticker['regularMarketPrice']
				pchange = ticker['regularMarketChangePercent']
		elif mstate == 'POST':
			try:
				price = ticker['postMarketPrice']
				pchange = ticker['postMarketChangePercent']
			except:
				price = ticker['regularMarketPrice']
				pchange = ticker['regularMarketChangePercent']
		else:
			print(f'??? mstate = {mstate}')

		try:
			ps = '+' if pchange >= 0 else ''
		except:
			ps = '='

		if mstate not in ('PREPRE', 'POSTPOST', 'CLOSED'):
			if symbol_vals[symbol][-1] >= price:
				d = colored('↓', 'red', attrs=['blink'])
			elif symbol_vals[symbol][-1] < price:
				d = colored('↑', 'green', attrs=['blink'])

			if pchange >= 0:
				color = 'green'
			elif pchange < 0:
				color = 'red'
		else:
			if pchange < 0:
				color = 'red'
				d = colored('↓', 'red', attrs=['dark'])
			else:
				color = 'green'
				d = colored('↑', 'green', attrs=['dark'])

		symbol_vals[symbol].append(price)

		mstate = {
			'PREPRE': '[CLOSED]',
			'PRE': '[PRE-MARKET]',
			'REGULAR': '[OPEN]',
			'POST': '[AFTER-HOURS]',
			'POSTPOST': '[CLOSED]',
			'CLOSED': '[CLOSED]'
		}[mstate]

		# format pchange
		pchange = f'{ps}{pchange:.2f}'

		if len(mstate) > mstatemaxlen:
			mstatemaxlen = len(mstate)

		if len(pchange) > pchmaxlen:
			pchmaxlen = len(pchange)

		# color individual parts
		if mstate != '[CLOSED]':
			symstr =  colored(f'{symbol:>{tmaxlen}} ', color, attrs=['bold'])
			pricestr = colored(f'{price:>{pmaxlen+1}.4f} {pchange:>{pchmaxlen+1}}%  {mstate}', color)
		else:
			symstr =  colored(f'{symbol:>{tmaxlen}} ', color, attrs=['bold', 'dark'])
			pricestr = colored(f'{price:>{pmaxlen+1}.4f} {pchange:>{pchmaxlen+1}}%  {mstate}', color, attrs=['dark'])

		printstr += f'{symstr} {d} {pricestr}\n'

	# add header
	symstr = colored(f'{"TICKER":>{tmaxlen}}  𝜹 ', attrs=['dark'])
	pricestr = colored(f'{"PRICE":>{pmaxlen+1-1}} {"CHANGE":>{pchmaxlen+2}}  {"MARKET":{mstatemaxlen}}', attrs=['dark'])
	printstr = f'\n{symstr} {pricestr}\n' + printstr

	# write to console
	sys.stdout.write(f'%s\r' % printstr)

	# move cursor up
	clear_str = "\033[A\033[A" * (len(tickers))
	sys.stdout.write(clear_str)


def datausage():
	usage = symbol_vals['DATA_USAGE']
	if usage/10**6 >= 1:
		data_suffix = 'GB' if usage/10**9 >= 1 else 'MB'
		usage = usage/10**9 if usage/10**9 >= 1 else usage/10**6
	else:
		data_suffix = 'KB'
		usage = usage/10**3

	return f'{usage:3.1f} {data_suffix}'


def load_config():
	if not os.path.isfile('pyticker-config.json'):
		with open('pyticker-config.json', 'w') as config_file:
			print('Enter the tickers you want to follow, separated by spaces (NOK NIO AAPL etc.)')
			inp = input('Enter tickers: ')
			symbols = inp.split(' ')

			if symbols == []:
				symbols = ['GME', 'NOK', 'NOKIA.HE']

			config = {
				'symbols': symbols
			}

			json.dump(config, config_file, indent=4)
			return config

	with open('pyticker-config.json', 'r') as config_file:
		try:
			return json.load(config_file)
		except ValueError:
			os.remove('pyticker-config.json')
			load_config()


if __name__ == '__main__':
	# load symbols
	cfg = load_config()
	symbols = cfg['symbols']
	#symbols = ('GME', 'NOK', 'BBAB', 'TSLA', 'AAPL', 'AMD', 'INTL', 'NOKIA.HE')

	# clear terminal
	cursor.hide()
	os.system('clear')

	# keep track of price for deltas, track data usage
	global symbol_vals
	symbol_vals = {symbol:[0] for symbol in symbols}
	symbol_vals['DATA_USAGE'] = 0

	# schedule api calls
	schedule.every(5).seconds.do(api_call, symbols=symbols)

	try:
		while True:
			rows0, columns0 = subprocess.check_output(['stty', 'size']).split()
			for char in ('⠷', '⠯', '⠟', '⠻', '⠽', '⠾'):
				sys.stdout.write('%s\r' % f'{colored(f"  pyTicker 0.1.0 | {datausage()} | quit: ctrl+c", attrs=["dark"])}')
				sys.stdout.write('\033[92m%s\r\033[0m' % char)

				time.sleep(0.2)
				schedule.run_pending()

			rows1, columns1 = subprocess.check_output(['stty', 'size']).split()
			if rows0 != rows1 or columns0 != columns1:
				os.system('clear')
	except KeyboardInterrupt:
		cursor.show()

	cursor.show()
	time.sleep(2)
