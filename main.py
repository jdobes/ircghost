#!/usr/bin/python3

import configparser
import logging
import socket


config = configparser.ConfigParser()
config.read("./config.ini")
config = config['DEFAULT']

logging.basicConfig(filename='./ircghost.log', level=logging.INFO)


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
        logging.info(ircmsg)


def pong(sock, to):
    sock.send(bytes("PONG " + to + "\r\n", "UTF-8"))


def sendmsg(sock, msg, target):
    sock.send(bytes("PRIVMSG " + target + " :" + msg + "\r\n", "UTF-8"))


def finish(sock):
    sock.send(bytes("QUIT :" + config['quitmsg'] + "\r\n", "UTF-8"))


def main():
    bot = connect(config['botnick'])
    channel = config['channel']
    joinchan(bot, channel)
    try:
        while 1:
            ircmsg = bot.recv(2048).decode("UTF-8")
            ircmsg = ircmsg.strip('\n\r')
            logging.info(ircmsg)
            parts = ircmsg.split()
            if parts[1] == "PRIVMSG":
                name_from = ircmsg.split('!', 1)[0][1:]
                name_to = ircmsg.split('PRIVMSG ', 1)[1].split(' :', 1)[0]
                message = ircmsg.split('PRIVMSG', 1)[1].split(':', 1)[1]
                words = message.split()
                # Repeat response from contact
                if name_from == config['ask'] and name_to == config['botnick']:
                    sendmsg(bot, message, config['channel'])
                # Regular chat message, parse (but not from contact itself if he is in channel)
                elif name_from != config['ask']:
                    for i, word in enumerate(words):
                        if word in ("rank", "srank") and i < (len(words) - 1):
                            sendmsg(bot, word + " " + words[i + 1], config['ask'])
                        elif word.endswith("++") or word.endswith("--"):
                            sendmsg(bot, word, config['ask'])
            elif parts[0] == "PING":
                    pong(bot, parts[1])
    except KeyboardInterrupt:
        finish(bot)


main()
