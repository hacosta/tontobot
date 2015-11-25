#!/usr/bin/python3
import sys
import subprocess
import re
import os
import os.path
import argparse
import itertools
import logging
import urllib.request
import urllib.parse
import lxml.html
import irc.bot
import irc.client
import random
import sqlite3
import configparser
import time
import collections
import datetime

DEFAULTS = {
		'server': 'irc.freenode.net',
		'nickname': 'tontobot',
		'channel': '#gultec',
		'realname': 'Tonto Bot',
		'port': 6667
		}

def get_urls(s):
	return re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', s)

class HttpManager():
	FETCH_MAX = 20 * 1024
	HEADER = {
		'User-agent': 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11'
	}

	def urlopen(self, url, maxbytes=FETCH_MAX):
		req = urllib.request.Request(url, headers=self.HEADER)
		fd = urllib.request.urlopen(req)
		return fd.read(maxbytes)

	def tinify(self, url):
		return self.urlopen('http://tinyurl.com/api-create.php?url=%s' % url).decode('utf-8')

	def paste(self, data):
		# pinchetontobot1337:pinchetontobot1337@sharklasers.com
		url = 'http://pastebin.com/api/api_post.php'
		ascii_params = {
			'api_paste_private': '1', # unlisted post
			'api_paste_name': 'Tontobot',
			'api_paste_expire_date': '1M', # 1 month lifespan
			'api_dev_key': 'c41f72ec503dced6de5422c00a792c44',
			'api_option': 'paste',
			'api_paste_code': data
		}
		urlencoded_params = urllib.parse.urlencode(ascii_params)
		binary_params = urlencoded_params.encode('utf-8')
		fd = urllib.request.urlopen(url, binary_params)
		url = fd.read()
		return url.decode('utf-8')

class SqlManager():
	URL_TABLE = '''urls (
		url TEXT PRIMARY KEY NOT NULL,
		title TEXT NOT NULL,
		user TEXT NOT NULL,
		time TEXT NOT NULL
	);'''
	
	def __init__(self, dbpath='./seenurls.db'):
		try:
			self.sqlcon = sqlite3.connect(dbpath)
			self.sqlcon.row_factory = sqlite3.Row
			self.sqlcur = self.sqlcon.cursor()
			self.sqlcon.execute('CREATE TABLE IF NOT EXISTS ' + self.URL_TABLE)
		except:
			logging.exception("Unable to open URL database!")
			raise

	def get_url_poster(self, url):
		self.sqlcur.execute('SELECT user FROM urls WHERE url = ?', (url,))
		sqlrow = self.sqlcur.fetchone()
		if sqlrow is not None:
			return sqlrow['user']
		return None

	def insert_url_metadata(self, url, title, user, time):
		self.sqlcur.execute('INSERT INTO urls VALUES (?,?,?,?)', (url, title, user, time.time(),))
		self.sqlcon.commit()

	def get_last_n_urls(self, n):
		self.sqlcur.execute('SELECT * FROM urls ORDER BY time DESC LIMIT ?', (n,))
		sqlrows = self.sqlcur.fetchall()
		return sqlrows

class TontoBot(irc.bot.SingleServerIRCBot):
	URL_MAXLEN = 60 # If url is longer than this, tontobot will request a tinified version of the url
	MSG_MAX = 140
	FAIL_MSGS = [':(', '):', '?', 'WAT', 'No pos no', 'link no worky', 'chupa limon']

	def __init__(self, serverspec, channel, nickname, realname):
		irc.bot.SingleServerIRCBot.__init__(self, [serverspec], nickname, realname)
		self.channel = channel
		logging.info("nickname=[%s] realname=[%s] channel=[%s]" % (nickname, realname, channel))
		self.httpm = HttpManager()
		self.sqlm = SqlManager()
	
	def on_welcome(self, connection, event):
		logging.debug("joining %s", self.channel)
		connection.join(self.channel)

	def _sendmsg(self, connection, msg):
		"""Convenience method to send a msg. Truncates msg to MSG_MAX chars"""
		msg = msg.replace('\n', ' ')
		logging.info("msg: %s" % msg)
		if len(msg) > 140:
			msg = msg[:self.MSG_MAX]
			logging.info("truncated msg: %s" % msg)
		connection.privmsg(self.channel, msg)

	def masca(self):
		openers = ('en serio que', 'neta que', 'al chile', '')
		haters = ('me caga', 'me re-caga', 'me molesta un chingo', 'está todo mal', 'me emputa', 'está todo gacho', 'es lo más ojete de la vida', 'es bien tonto')
		closers = ('que fecal fue presidente', 'que no uses C', 'que uses camelCase', 'que existas', 'que un lenguaje no tenga apuntadores', 'que amlo perdió', '')
		standalones = ('Viva el EZLN', '¬¬', '¡Viva la revolución!', 'Estás todo gacho', 'Vamos por cheve')

		composed_len = len(openers) * len(haters) * len(closers)
		totlen = composed_len + len(standalones)

		logging.info('totlen = %d' % totlen)
		logging.info('composed_len = %d' % composed_len)
		# Give equal weight to standalones and composed. This should make standalones a relatively rare occurrence
		if random.randint(0, totlen) < composed_len:
			now = time.clock()
			quote = ' '.join(random.choice(list(itertools.product(openers, haters, closers)))).strip()
			end = time.clock()
			logging.info('Took %d seconds to generate a quote' % ( now - end))
			return quote
		else:
			return random.choice(standalones)

	def rtfm(self, line):
		argv = line.split()
		if len(argv) == 3:
			cmd = argv[2].strip()
			section = argv[1]
		elif len(argv) == 2:
			cmd = argv[1].strip()
			section = None
		else:
			raise Exception("format: !rtfm [section] cmd")

		if not re.match('^[a-zA-Z_-]+$', cmd):
			logging.error("re.match rtfm: %s" % cmd)
			raise Exception("Funky commands not supported")

		if section:
			stdout = subprocess.check_output(['man', '--pager', 'cat', str(section), cmd])
		else:
			stdout = subprocess.check_output(['man', '--pager', 'cat', cmd])
		stdout = stdout.decode('utf-8')

		if stdout:
			seen_description = False
			for line in stdout.splitlines():
				line = line.strip()
				if seen_description:
					return line.split('.')[0]
				if line.endswith('DESCRIPTION'):
					seen_description = True
			raise Exception("Unable to parse manpage")

		raise Exception("No man page found")

	def last(self, line):
		"""Gets the last n URLs' metadata"""
		argv = line.split()
		if len(argv) == 2:
			n = argv[1].strip()
		else:
			raise Exception("format: !last n")

		try:
			n = int(n)
		except ValueError:
			logging.error("last n: %s" % n)
			raise Exception("n must be an integer")
		
		sqlrows = self.sqlm.get_last_n_urls(n)
		if sqlrows is not None:
			s = ''
			for row in sqlrows:
				s += row['user'] + ': ' + row['url'] + '\n'
			pasteurl = self.httpm.paste(s)
		else:
			raise Exception("No URLs to fetch")
		return pasteurl
	def logs(self,line):
		argv = line.split()
		if len(argv) == 2:
			if len(argv[1]) == 8:
				year = argv[1][:4]
				month = argv[1][4:6]
				day = argv[1][-2:]
				try:
					inputDate = datetime.datetime(int(year),int(month),int(day))
					datedelta = datetime.datetime.today() - inputDate
				except ValueError:
					return "that date is not valid!"
				if datedelta > datetime.timedelta(microseconds=1):
					logurl = "http://irclogs.gultec.org/gultec-"+year+"-"+month+"-"+day
					return logurl
				else:
					return "back to the future!"
			else:
				return "usage: !logs yyyymmdd"
		else:
			return "usage: !logs yyyymmdd"
		
	def on_pubmsg(self, connection, event):
		line = event.arguments[0]
		user = event.source.split('!')[0]
		try:
			if line.startswith('!last'):
				self._sendmsg(connection, self.last(line))
			elif line.startswith('!rtfm'):
				self._sendmsg(connection, self.rtfm(line))
			elif line.startswith('!masca'):
				self._sendmsg(connection, self.masca())
			elif line.startswith('ping'):
				self._sendmsg(connection, 'pong')
			elif line.startswith('!logs'):
				self._sendmsg(connection, self.logs(line))
		except:
			logging.exception("Failed with: %s" % line)
		for url in get_urls(line):
			msg = collections.deque()
			try:
				if url.endswith(('.jpg', '.png', '.git', '.bmp', '.pdf')):
					logging.info('not a webpage, skipping')
					continue
				root = lxml.html.fromstring(self.httpm.urlopen(url))
				title = root.find('.//title').text
				p = self.sqlm.get_url_poster(url)
				if p is not None:
					msg.append('[repost: %s]' % p)
				else:
					self.sqlm.insert_url_metadata(url, title, user, time)
				if len(url) > self.URL_MAXLEN:
					msg.append('[%s]' % self.httpm.tinify(url))
				msg.append(title)
				self._sendmsg(connection, ' '.join(msg))
			except:
				logging.exception("Failed with: %s" % line)
				self._sendmsg(connection, random.choice(self.FAIL_MSGS))

def get_args():
	parser = argparse.ArgumentParser()
	parser.add_argument('--server')
	parser.add_argument('--nickname')
	parser.add_argument('--channel')
	parser.add_argument('--realname')
	parser.add_argument('-p', '--port', type=int)
	return parser.parse_args()


def main():
	logging.basicConfig(level=logging.INFO)
	config = configparser.ConfigParser()
	config.read(['./tontorc', os.path.expanduser('~/.tontorc')])
	args = get_args()

	server = args.server or config['net'].get('server', DEFAULTS['server'])
	nickname = args.nickname or config['net'].get('nickname', DEFAULTS['nickname'])
	channel = args.channel or config['net'].get('channel', DEFAULTS['channel'])
	realname = args.realname or config['net'].get('realname', DEFAULTS['realname'])
	port = args.port or config['net'].getint('port', DEFAULTS['port'])

	# Do not try to decode lines
	irc.buffer.DecodingLineBuffer.errors = 'replace'
	serverspec = irc.bot.ServerSpec(server, port)
	bot = TontoBot(serverspec, channel, nickname, realname)
	try:
		c = bot.start()
	except irc.client.ServerConnectionError:
		logging.error((sys.exc_info()[1]))
		sys.exit(1)

if __name__ == '__main__':
	main()
