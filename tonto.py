#!/usr/bin/python3
import sys
import re
import argparse
import itertools
import logging
import bs4
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
		logging.info("channel= %s" % channel)
		try:
			with open(seen_urlpath, 'rb') as f:
				self.urlhist = pickle.load(f)
		except:
			self.urlhist = {}
		self.urlfd = 

	def on_welcome(self, connection, event):
		logging.info("joining %s", self.channel)
		connection.join(self.channel)

	def _best_effort_send(self, connection, msg):
		try:
			connection.privmsg(self.channel, random.choice(self.FAIL_MSGS))
		except:
			pass


	def on_pubmsg(self, connection, event):
		line = event.arguments[0]
		opener = urllib.request.build_opener()
		opener.add_headers = [('User-agent', 'Mozilla/5.0')]
		for u in get_urls(line):
			try:
				fd = opener.open(u)
				soup = bs4.BeautifulSoup(fd.read(self.FETCH_MAX))
				title = soup.title.string
				if title in self.urlhist:
					connection.privmsg(self.channel, "[repost] " + title)
				else:
					connection.privmsg(self.channel, title)
				with open(
				picke.dump(self.urlhist):
			except:
				logging.exception("Failed with: %s" % line)
				self._best_effort_send(connection, random.choice(self.FAIL_MSGS))

def get_args():
	parser = argparse.ArgumentParser()
	parser.add_argument('--server', default='irc.freenode.net')
	parser.add_argument('--nickname', default='tontobot')
	parser.add_argument('--channel', default='#gultec2')
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
