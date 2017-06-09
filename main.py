#!/usr/bin/python3

import configparser
import logging
import socket
from threading import Thread


config = configparser.ConfigParser()
config.read("./config.ini")
config = config['DEFAULT']

if int(config['log_debug'] or 0):
    level = logging.DEBUG
else:
    level = logging.INFO

logging.basicConfig(filename='./ircghost.log', level=level)

user_aliases = {}
user_threads = {}


def connect(nick):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((config['server'], int(config['port'])))
    sock.send(bytes("USER " + nick + " " + nick + " " + nick + " " + nick + "\r\n", "UTF-8"))
    sock.send(bytes("NICK " + nick + "\r\n", "UTF-8"))
    return sock


def joinchan(sock, chan):
    sock.send(bytes("JOIN " + chan + "\r\n", "UTF-8"))
    ircmsg = ""
    while ircmsg.find("End of /NAMES list.") == -1:
        ircmsg = sock.recv(2048).decode("UTF-8")
        ircmsg = ircmsg.strip('\n\r')
        logging.debug(ircmsg)


def pong(sock, to):
    sock.send(bytes("PONG " + to + "\r\n", "UTF-8"))


def sendmsg(sock, msg, target):
    request = "PRIVMSG " + target + " :" + msg + "\r\n"
    logging.debug("Sending: " + request)
    sock.send(bytes(request, "UTF-8"))


def finish(sock):
    sock.send(bytes("QUIT :" + config['quitmsg'] + "\r\n", "UTF-8"))
    sock.close()


class IrcThread(Thread):
    def __init__(self, nick, messages):
        Thread.__init__(self)
        self.nick = nick
        self.sock = connect(nick)
        self.sock.settimeout(5)
        joinchan(self.sock, config['home_channel'])
        self.messages = messages

    def run(self):
        for message in self.messages:
            sendmsg(self.sock, message, config['ask'])
        while 1:
            try:
                ircmsg = self.sock.recv(2048).decode("UTF-8")
            except socket.timeout:
                logging.info("Nothing received, shutting thread down.")
                break
            ircmsg = ircmsg.strip('\n\r')
            parts = ircmsg.split()
            if parts[1] == "PRIVMSG":
                name_from = ircmsg.split('!', 1)[0][1:]
                name_to = ircmsg.split('PRIVMSG ', 1)[1].split(' :', 1)[0]
                message = ircmsg.split('PRIVMSG', 1)[1].split(':', 1)[1]
                # Response from karma bot
                if name_from == config['ask'] and name_to == self.nick:
                    sendmsg(self.sock, message, config['botnick'])
            elif parts[0] == "PING":
                pong(self.sock, parts[1])
        finish(self.sock)


def thread_send(sock, name_from, msgs):
    if name_from not in user_threads or not user_threads[name_from].isAlive():
        if name_from not in user_aliases:
            new_user = config['karma_user_prefix'] + str(len(user_aliases))
            user_aliases[name_from] = new_user
        else:
            new_user = user_aliases[name_from]
        new_thread = IrcThread(new_user, msgs)
        new_thread.setDaemon(True)
        new_thread.start()
        user_threads[name_from] = new_thread
    else:
        logging.info("User thread is running, skipping.")


def main():
    bot = connect(config['botnick'])
    joinchan(bot, config['home_channel'])
    if config['channel']:
        joinchan(bot, config['channel'])
    try:
        while 1:
            ircmsg = bot.recv(2048).decode("UTF-8")
            ircmsg = ircmsg.strip('\n\r')
            parts = ircmsg.split()
            if parts[1] == "PRIVMSG":
                name_from = ircmsg.split('!', 1)[0][1:]
                message = ircmsg.split('PRIVMSG', 1)[1].split(':', 1)[1]
                words = message.split()
                # Repeat response from contact
                if name_from in user_aliases.values():
                    sendmsg(bot, message, config['home_channel'])
                # Regular chat message, parse (but not from contact itself if he is in channel)
                elif name_from != config['ask']:
                    filtered_msgs = []
                    for i, word in enumerate(words):
                        if word in ("rank", "srank") and i < (len(words) - 1):
                            filtered_msgs.append(word + " " + words[i + 1])
                        elif word.endswith("++") or word.endswith("--"):
                            filtered_msgs.append(word)
                    if filtered_msgs:
                        thread_send(bot, name_from, filtered_msgs)
            elif parts[0] == "PING":
                    pong(bot, parts[1])
    except KeyboardInterrupt:
        finish(bot)


main()
