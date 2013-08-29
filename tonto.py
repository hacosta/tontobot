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
import lxml.html
import irc.bot
import irc.client
import random
import pickle
import atexit
import configparser
import time
import collections

DEFAULTS = {
		'server': 'irc.freenode.net',
		'nickname': 'tontobot',
		'channel': '#gultec',
		'realname': 'Tonto Bot',
		'port': 6667
		}

def get_urls(s):
	return re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', s)

class TontoBot(irc.bot.SingleServerIRCBot):
	FETCH_MAX = 20 * 1024
	URL_MAXLEN = 60 # If url is longer than this, tontobot will provide a tinified version of the url
	MSG_MAX = 140
	FAIL_MSGS = [':(', '):', '?', 'WAT', 'No pos no', 'link no worky', 'chupa limon']

	def __init__(self, serverspec, channel, nickname, realname, seen_urlpath='./seenurls.pickle'):
		irc.bot.SingleServerIRCBot.__init__(self, [serverspec], nickname, realname)
		self.channel = channel
		self.seen_urlpath = seen_urlpath
		logging.info("nickname=[%s] realname=[%s] channel=[%s]" % (nickname, realname, channel))
		try:
			with open(seen_urlpath, 'rb') as f:
				self.urlhist = pickle.load(f)
		except:
			self.urlhist = {}
		atexit.register(self._dumphist)

	def on_welcome(self, connection, event):
		logging.debug("joining %s", self.channel)
		connection.join(self.channel)

	def _sendmsg(self, connection, msg):
		"""Convenience method to send a msg. Truncates msg to MSG_MAX chars"""
		msg = msg.replace('\n', ' ')
		logging.info("msg: %s" % msg)
		if len(msg) > 140:
			msg = msg[self.MSG_MAX:]
			logging.info("truncated msg: %s" % msg)
		connection.privmsg(self.channel, msg)

	def _dumphist(self):
		try:
			with open(self.seen_urlpath, 'wb') as f:
				pickle.dump(self.urlhist, f)
		except:
			logging.exception("Oh noes, history is lost")

	def urlopen(self, url, maxbytes=FETCH_MAX):
		req = urllib.request.Request(url, headers={'User-agent': 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11'})
		fd = urllib.request.urlopen(req)
		return fd.read(maxbytes)

	def tinify(self, url):
		return self.urlopen('http://tinyurl.com/api-create.php?url=%s' % url).decode('utf-8')

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

	def on_pubmsg(self, connection, event):
		line = event.arguments[0]
		try:
			if line.startswith('!rtfm'):
				self._sendmsg(connection, self.rtfm(line))
			elif line.startswith('!masca'):
				self._sendmsg(connection, self.masca())
			elif line.startswith('ping'):
				self._sendmsg(connection, 'pong')
		except:
			logging.exception("Failed with: %s" % line)
		for u in get_urls(line):
			msg = collections.deque()
			try:
				if u.endswith(('.jpg', '.png', '.git', '.bmp', '.pdf')):
					logging.info('not a webpage, skipping')
					continue
				root = lxml.html.fromstring(self.urlopen(u))
				title = root.find('.//title').text
				if u in self.urlhist:
					msg.append('[repost]')
				else:
					self.urlhist[u] = title
				if len(u) > self.URL_MAXLEN:
					msg.append('[%s]' % self.tinify(u))
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
		log.error((sys.exc_info()[1]))
		raise SystemExit(1)

if __name__ == '__main__':
	main()
