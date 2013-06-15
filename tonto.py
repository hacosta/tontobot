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

	def _best_effort_send(self, connection, msg):
		try:
			connection.privmsg(self.channel, random.choice(self.FAIL_MSGS))
		except:
			pass

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

	def masca(self):
		return random.choice(['rant rant rant', 'al chile me caga', 'estás todo mal',
			'me emputa', '¡Viva la revolución!', 'izq. izq', 'EZLN, etc.', 'es culpa de fecal',
			'SeVeTodoFeo', 'no tiene apuntadores'])

	def rtfm(self, line):
		argv = line.split()
		if len(argv) == 3:
			cmd = argv[2].strip()
			section = argv[1]
		elif len(line.split()) == 2:
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
				connection.privmsg(self.channel, self.rtfm(line))
			elif line.startswith('!masca'):
				connection.privmsg(self.channel, self.masca())
			elif line.startswith('ping'):
				connection.privmsg(self.channel, 'pong')
		except:
			logging.exception("Failed with: %s" % line)
		for u in get_urls(line):
			try:
				root = lxml.html.fromstring(self.urlopen(u))
				title = root.find('.//title').text
				if u in self.urlhist:
					connection.privmsg(self.channel, "[repost] " + title)
				else:
					connection.privmsg(self.channel, title)
					self.urlhist[u] = title
			except:
				logging.exception("Failed with: %s" % line)
				self._best_effort_send(connection, random.choice(self.FAIL_MSGS))

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
