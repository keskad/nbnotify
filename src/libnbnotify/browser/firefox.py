#!/usr/bin/env python
""" Simple class to get cookies from Firefox web browser """

import libnbnotify.browser
import os
import sqlite3
import shutil
import hashlib
import glob
import sys

# debugging
#import __init__
#nbCookie = __init__.nbCookie

class BrowserError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)

class MySum:
    """ Counting results class for SQLite3 """

    def __init__(self):
        self.count = 0

    def step(self, value):
        self.count += value

    def finalize(self):
        return self.count

class nbBrowser:
    profile = None
    path = os.path.expanduser('~/.mozilla/firefox')
    profile = 'default'
    tmp = ""

    def __init__(self):
        if not os.path.isdir(self.path):
            BrowserError("Cannot find Firefox configuration files in "+self.path)


    def dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d


    def listProfiles(self):
        """ Returns list of avaliable profiles """

        profiles = os.listdir(self.path)

        verifiedProfiles = list()

        for d in profiles:
            r = d.split(".")

            if not os.path.isfile(self.path+'/'+d+'/cookies.sqlite'):
                continue

            verifiedProfiles.append(r[1])

        return verifiedProfiles
        

    def load(self, profile='default'):
        f = glob.glob(self.path+"/*."+self.profile)

        if len(f) > 0:
            self.profile = os.path.basename(f[0])
        else:
            return False

        if os.path.isfile(self.path+'/'+self.profile+'/cookies.sqlite'):
            self.tmp = "/tmp/.nbfx."+hashlib.md5("firefox-"+self.profile+"-cookies").hexdigest()
            shutil.copyfile(self.path+'/'+self.profile+'/cookies.sqlite', self.tmp)

            #if os.name == "posix":
            os.chmod(self.tmp, 0700)

            self.socket = sqlite3.connect(self.tmp, check_same_thread = False)
            self.socket.create_aggregate("mysum", 1, MySum)
            self.socket.isolation_level = None
            self.socket.row_factory = self.dict_factory
            self.socket.text_factory = str
            self.cursor = self.socket.cursor()

            return True
        return False

    def getCookie(self, domain):
        query = self.cursor.execute("SELECT * FROM `moz_cookies` WHERE `host`='"+domain+"' OR `host`='."+domain+"';")

        cookies = list()

        for cookie in query.fetchall():
            cookies.append({'host': cookie['host'], 'name': cookie['name'], 'value': cookie['value'], 'path': cookie['path'], 'expires': cookie['expiry']})

        return libnbnotify.browser.nbCookie(cookies)


    def __del__(self):
        if self.tmp != "":
            os.remove(self.tmp)


#b = nbBrowser()
#print b.listProfiles()
#b.load()
#print b.getCookie("facebook.com").toCookieHeader()




