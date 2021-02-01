import os
import sys
import time
import subprocess
import logging

from datetime import datetime

import cursor
import schedule
import bashplotlib
import requests

from termcolor import colored

import numpy as np
import ujson as json


def api_call(tickers):
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
	requrl = f"{endpoint}&fields={','.join(flds)}&symbols={','.join(tickers)}"

	# do request
	API_RESPONSE = requests.get(requrl)
	api_json = json.loads(API_RESPONSE.text)

	data_dict['DATA_USAGE'] += len(API_RESPONSE.content)

	print_tickers(tickers=api_json['quoteResponse']['result'])

def shift(arr, num, fill_value=np.nan):
	result = np.empty_like(arr)
	if num > 0:
		result[:num] = fill_value
		result[num:] = arr[:-num]
	elif num < 0:
		result[num:] = fill_value
		result[:num] = arr[-num:]
	else:
		result[:] = arr

	return result

def print_tickers(tickers):
	tmaxlen = max([len(ticker['symbol']) for ticker in tickers])
	if tmaxlen < len('TICKER'):
		# make sure the header fits
		tmaxlen = len('TICKER')

	# max lens for prettier prints
	pmaxlen = max([len(f"{ticker['regularMarketPrice']:.4f}") for ticker in tickers])
	mstatemaxlen, pchmaxlen = 0, 0

	# find the next index we store the price data in (here, so we only do it once)
	random_ticker = list(data_dict.keys())[0]
	empty_indices = np.where(
		np.isnan(data_dict[random_ticker])
	)

	if empty_indices[0].size == 0:
		for key, arr in data_dict.items():
			if key != 'DATA_USAGE':
				data_dict[key] = shift(arr=arr, num=1)

		next_empty = -1
	else:
		next_empty = empty_indices[0][0]

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

		if mstate in ('PREPRE', 'POSTPOST', 'CLOSED'):
			if pchange < 0:
				color = 'red'
				d = colored('↓', 'red', attrs=['dark'])
			else:
				color = 'green'
				d = colored('↑', 'green', attrs=['dark'])
		else:
			# next_empty - 1
			idx = next_empty - 1 if next_empty - 1 >= 0 else 0

			if data_dict[symbol][idx] >= price:
				d = colored('↓', 'red')
			elif data_dict[symbol][idx] < price:
				d = colored('↑', 'green')
			else:
				d = colored('↑', 'green')

			if pchange >= 0:
				color = 'green'
			elif pchange < 0:
				color = 'red'

		# store price in next free index
		data_dict[symbol][next_empty] = price

		mstate = {
			'PREPRE': '[CLOSED]',
			'PRE': '[PRE-MARKET]',
			'REGULAR': '[OPEN]',
			'POST': '[AFTER-HOURS]',
			'POSTPOST': '[CLOSED]',
			'CLOSED': '[CLOSED]'
		}[mstate]

		# format pchange
		pchange = f'{ps}{pchange:.2f}%'

		if len(mstate) > mstatemaxlen:
			mstatemaxlen = len(mstate)

		if len(pchange) > pchmaxlen:
			pchmaxlen = len(str(pchange)) + 1

		# color individual parts
		if mstate != '[CLOSED]':
			symstr =  colored(f'{symbol:>{tmaxlen}} ', color, attrs=['bold'])
			pricestr = colored(f'{price:>{pmaxlen}.4f}  {pchange:>{pchmaxlen}}  {mstate}', color)
		else:
			symstr =  colored(f'{symbol:>{tmaxlen}} ', color, attrs=['bold', 'dark'])
			pricestr = colored(f'{price:>{pmaxlen}.4f}  {pchange:>{pchmaxlen}}  {mstate}', color, attrs=['dark'])

		printstr += f'{symstr} {d} {pricestr}\n'

	# add header
	symstr = colored(f'{"TICKER":>{tmaxlen}}  𝜹 ')
	pricestr = colored(f'{"PRICE":>{pmaxlen}} {"DAY":>{pchmaxlen}}  {"MARKET":<{mstatemaxlen}}')
	printstr = f'\n{symstr} {pricestr}\n' + printstr

	# write to console
	sys.stdout.write('%s\r' % printstr)

	# move cursor up
	clear_str = "\033[A\033[A" * (len(tickers))
	sys.stdout.write(clear_str)


def datausage():
	usage = data_dict['DATA_USAGE']
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
			_symbols = inp.split(' ')

			if _symbols == []:
				_symbols = ['GME', 'NOK', 'NOKIA.HE']

			config = {
				'symbols': _symbols
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
	'''
	TODO
	- only store x latest price points in data_dict to keep memory usage relatively low
		- optimize by preallocating: preallocated numpy arrays? (np.empty)
		- preallocate for 1 hour of data points (or whatever is chosen for plot range)
		- dump array on exit -> sqlite or something
	- throttle api calls if all tickers are in closed markets
	- split by market
		- show local market time + offset
		- show time until next open/close
	- add trailing 5, 15, 1 hour delta (% + arrow)
		- replace "CHANGE" with "DAY" -> add "5", "15", "60"
	'''
	VERSION = '0.1.2'
	logging.basicConfig(
		filename='pyticker-log.log', level=logging.DEBUG,
		format='%(asctime)s %(message)s',
		datefmt='%d/%m/%Y %H:%M:%S')

	logging.getLogger('requests').setLevel(logging.CRITICAL)
	logging.getLogger('urllib3').setLevel(logging.CRITICAL)
	logging.getLogger('schedule').setLevel(logging.CRITICAL)
	logging.getLogger('chardet.charsetprober').setLevel(logging.CRITICAL)

	# clear terminal
	os.system('clear')

	# load symbols
	cfg = load_config()
	symbols = cfg['symbols']
	logging.info(f'pyticker {VERSION} started, tracking symbols: {", ".join(symbols)}')

	# track the trailing 1 hour of data: use refresh interval to determine
	# required amount of data points
	upd_sec = 5
	idx_count = int(3600/upd_sec)

	# keep track of price for deltas, track data usage
	global data_dict
	data_dict = {symbol:np.empty(idx_count) for symbol in symbols}
	data_dict['DATA_USAGE'] = 0

	# fill with nans
	for key, arr in data_dict.items():
		if key != 'DATA_USAGE':
			arr[:] = np.nan

	# schedule api calls
	schedule.every(upd_sec).seconds.do(api_call, tickers=symbols)
	api_call(tickers=symbols)

	cursor.hide()

	try:
		while True:
			rows0, columns0 = subprocess.check_output(['stty', 'size']).split()
			for char in ('⠷', '⠯', '⠟', '⠻', '⠽', '⠾'):
				sys.stdout.write('%s\r' % f'{colored(f"  pyticker {VERSION} | {datausage():8} | quit: ctrl+c", attrs=["dark"])}')
				sys.stdout.write('\033[92m%s\r\033[0m' % char)

				time.sleep(0.2)
				schedule.run_pending()

			rows1, columns1 = subprocess.check_output(['stty', 'size']).split()
			if rows0 != rows1 or columns0 != columns1:
				os.system('clear')
	except KeyboardInterrupt:
		cursor.show()

	cursor.show()
	os.system('clear')
