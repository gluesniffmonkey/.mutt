#!/usr/bin/env python
# coding: utf-8
# imap-idle for mbsync (or other imap sync)
# copyright (c) 2016, Gabriel Pettier
# usage:
# - edit the MBSYNC, GPG_COMMAND, POST_SYNC_COMMANDS and conf variables
# to suit your configuration
# - run imap_idle.py
# BSD licensed
# Please see http://en.wikipedia.org/wiki/BSD_licenses

from imapclient import IMAPClient
from time import sleep
from subprocess import Popen, check_output
from colorama import Fore, Style
from sys import argv
from time import asctime
import click
import libtmux

from imap_idle_conf import MBSYNC, POST_SYNC_COMMANDS, conf


def icheck_output(*args, **kwargs):
    print("calling, {}, {}".format(' '.join(map(str, args)), kwargs))
    process = Popen(*args, **kwargs)
    process.wait()


def _idle_client(account, box):
    c = conf[account]
    if 'pass_cmd' in c:
        c['pass'] = check_output([c['pass_cmd']], shell=True).strip()
    client = IMAPClient(
        c['host'], use_uid=True, ssl=c['ssl'])
    client.login(c['user'], c['pass'])
    try:
        client.select_folder(box)
    except:
        print(Style.BRIGHT + Fore.RED +
              "unable to select folder {}".format(box) +
              Fore.RESET + Style.RESET_ALL)
        return
    client.idle()

    print("connected, {}: {}".format(account, box))
    while True:
        for m in client.idle_check():
            if m != (b'OK', b'Still here'):
                print(Style.BRIGHT + Fore.GREEN,
                      "event: {}, {}, {}".format(account, box, m) +
                      Fore.RESET + Style.RESET_ALL)
                sync(c['local'], box)
        sleep(1)


def spawn_client(window, account, box, split=True):
    if split:
        panel = window.split_window()
    else:
        panel = window.list_panes()[0]
    window.select_layout('even-vertical')
    panel.clear()
    panel.send_keys(u'%s client "%s" "%s"' % (argv[0], account, box))


@click.group()
def cli():
    pass


def sync(host=None, box=None):
    if not host:
        print("initial sync" + Fore.LIGHTWHITE_EX + Style.DIM)
        icheck_output([MBSYNC, '-a'])
    else:
        print(Style.BRIGHT + Fore.CYAN +
              "syncing: {}:{}".format(host, box) +
              Fore.LIGHTWHITE_EX + Style.RESET_ALL + Style.DIM)
        icheck_output([MBSYNC, '{}:{}'.format(host, box)])

        print(Style.RESET_ALL + Style.BRIGHT + Fore.CYAN +
              "done syncing {}:{}".format(host, box) +
              Fore.RESET + Style.RESET_ALL)

    for c in POST_SYNC_COMMANDS:
        print(Fore.YELLOW + Style.BRIGHT)
        icheck_output(c)
        print(Style.RESET_ALL + Fore.RESET)

    print(Fore.BLUE + Style.BRIGHT +
          "last sync of %s:%s at %s" % (host, box, asctime()) +
          Style.RESET_ALL + Fore.RESET)


@cli.command('client')
@click.argument('account')
@click.argument('box')
def idle_client(account, box):
    """connect to account and wait for events on box to sync
    """
    while True:
        try:
            print(Style.BRIGHT + Fore.GREEN +
                  "connecting to {}:{}".format(account, box) +
                  Style.RESET_ALL + Fore.RESET)
            _idle_client(account, box)
        except Exception as e:
            print(Style.BRIGHT + Fore.RED +
                  "error {} in {}:{} connection, restarting"
                  .format(e, account, box) +
                  Fore.RESET + Style.RESET_ALL)


@cli.command('manager')
def main():
    """Sync all the mailboxes, then spawn clients for monitored mailboxes
    """
    sync()
    server = libtmux.Server()
    try:
        session = server.find_where({'session_name': 'mailsync'})
    except:
        session = None

    if not session:
        session = server.new_session('mailsync')

    window = session.list_windows()[0]

    # window.send_keys('%s sync')
    i = 0
    for account, c in conf.items():
        for box in c['boxes']:
            spawn_client(window, account, box, split=bool(i))
            i += 1

    session.attach_session()
