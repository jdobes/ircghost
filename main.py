#!/usr/bin/python3

import configparser
import logging
import socket
import time


config = configparser.ConfigParser()
config.read("./config.ini")
config = config['DEFAULT']

if int(config['log_debug'] or 0):
    level = logging.DEBUG
else:
    level = logging.INFO

logging.basicConfig(filename='./ircghost.log', level=level)

karma_requests = {}


def connect(nick):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((config['server'], int(config['port'])))
    sock.settimeout(int(config['socket_timeout']))
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


def where_to_send_response(channels, name_from, name_to):
    # Check if the request message was send to channel or directly to bot
    if name_to in channels or name_to == config['home_channel']:
        return name_to
    else:
        return name_from


def register_karma_request(word, respond_to):
    if word not in karma_requests:
        karma_requests[word] = set()
    karma_requests[word].add((time.time(), respond_to))


def main():
    bot = connect(config['botnick'])
    joinchan(bot, config['home_channel'])
    channels = config['channels'].split()
    for channel in channels:
        joinchan(bot, channel)
    try:
        while 1:
            try:
                ircmsg = bot.recv(2048).decode("UTF-8")
            except socket.timeout:
                ircmsg = None
            # Something received
            if ircmsg:
                ircmsg = ircmsg.strip('\n\r')
                parts = ircmsg.split()
                if parts[1] == "PRIVMSG":
                    name_from = ircmsg.split('!', 1)[0][1:]
                    name_to = ircmsg.split('PRIVMSG ', 1)[1].split(' :', 1)[0]
                    message = ircmsg.split('PRIVMSG', 1)[1].split(':', 1)[1]
                    words = message.split()
                    # Repeat response from contact to original channel
                    if name_from == config['ask'] and name_to == config['botnick']:
                        karma_keyword = None
                        # rank, ++/--
                        if len(words) > 3 and words[1] == "has" or words[2] == "has":
                            karma_keyword = words[0]
                        # need to wait
                        elif len(words) > 14 and words[4] == "wait":
                            karma_keyword = words[13][:-2]

                        if karma_keyword:
                            if karma_keyword in karma_requests:
                                respond_to = karma_requests[karma_keyword]
                                del karma_requests[karma_keyword]
                                for target in respond_to:
                                    sendmsg(bot, message, target[1])
                            else:
                                # WTF
                                sendmsg(bot, "Received unexpected karma message:", config['home_channel'])
                                sendmsg(bot, message, config['home_channel'])
                        else:
                            sendmsg(bot, message, config['home_channel'])
                    # Regular chat message, parse if it's sane
                    elif name_to in channels or name_to == config['home_channel'] or name_to == config['botnick']:
                        respond_to = where_to_send_response(channels, name_from, name_to)
                        for i, word in enumerate(words):
                            if word == "rank" and i + 1 <= (len(words) - 1):
                                register_karma_request(words[i + 1], respond_to)
                                sendmsg(bot, "%s %s" % (word, words[i + 1]), config['ask'])
                            elif word.endswith("++") or word.endswith("--"):
                                register_karma_request(word[:-2], respond_to)
                                sendmsg(bot, word, config['ask'])
                elif parts[0] == "PING":
                        pong(bot, parts[1])
            else:
                # Cleanup old requests
                empty_keys = []
                for key, targets in karma_requests.items():
                    to_delete = []
                    for target in targets:
                        if time.time() > target[0] + int(config['cleanup_timeout']):
                            to_delete.append(target)
                    for item in to_delete:
                        targets.remove(item)
                    if not targets:
                        empty_keys.append(key)
                for key in empty_keys:
                    del karma_requests[key]

    except KeyboardInterrupt:
        finish(bot)


main()
