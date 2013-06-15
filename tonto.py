#!/usr/bin/python3
import sys
import subprocess
import re
import os
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

def get_urls(s):
	return re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', s)

class TontoBot(irc.bot.SingleServerIRCBot):
	FETCH_MAX = 20 * 1024
	FAIL_MSGS = [':(', '):', '?', 'WAT', 'No pos no', 'link no worky', 'chupa limon']

	def __init__(self, serverspec, channel, nickname, realname, seen_urlpath='./seenurls.pickle'):
		irc.bot.SingleServerIRCBot.__init__(self, [serverspec], nickname, realname)
		self.channel = channel
		self.seen_urlpath = seen_urlpath
		logging.info("channel= %s" % channel)
		try:
			with open(seen_urlpath, 'rb') as f:
				self.urlhist = pickle.load(f)
		except:
			self.urlhist = {}
		atexit.register(self._dumphist)

	def on_welcome(self, connection, event):
		logging.info("joining %s", self.channel)
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
	parser.add_argument('--server', default='irc.freenode.net')
	parser.add_argument('--nickname', default='tontobot')
	parser.add_argument('--channel', default='#gultec')
	parser.add_argument('--realname', default='Tonto Bot')
	parser.add_argument('-p', '--port', default=6667, type=int)
	return parser.parse_args()


def main():
	logging.basicConfig(level=logging.INFO)
	args = get_args()
	# Do not try to decode lines
	irc.buffer.DecodingLineBuffer.errors = 'replace'
	serverspec = irc.bot.ServerSpec(args.server, args.port)
	bot = TontoBot(serverspec, args.channel, args.nickname, args.realname)
	try:
		c = bot.start()
	except irc.client.ServerConnectionError:
		log.error((sys.exc_info()[1]))
		raise SystemExit(1)

if __name__ == '__main__':
	main()
