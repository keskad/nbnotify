#!/usr/bin/env python
""" Simple class to get cookies from Chromium web browser """

import libnbnotify.browser
import os
import sqlite3
import shutil
import hashlib

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
    chromiumPath = os.path.expanduser('~/.config/chromium')
    profile = 'Default'
    tmp = ""

    def __init__(self):
        if not os.path.isdir(self.chromiumPath):
            BrowserError("Cannot find Chromium configuration files in "+self.chromiumPath)


    def dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d


    def listProfiles(self):
        """ Returns list of avaliable profiles """

        profiles = os.listdir(self.chromiumPath)

        verifiedProfiles = list()

        for d in profiles:
            if not os.path.isfile(self.chromiumPath+'/'+d+'/Cookies'):
                continue

            verifiedProfiles.append(d)

        return verifiedProfiles
        

    def load(self, profile='Default'):
        self.Profile = profile

        if os.path.isfile(self.chromiumPath+'/'+self.profile+'/Cookies'):
            self.tmp = "/tmp/.nbchromium."+hashlib.md5("chromium-"+self.profile+"-cookies").hexdigest()
            shutil.copyfile(self.chromiumPath+'/'+self.profile+'/Cookies', self.tmp)

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
        query = self.cursor.execute("SELECT * FROM `cookies` WHERE `host_key`='"+domain+"' OR `host_key`='."+domain+"';")

        cookies = list()

        for cookie in query.fetchall():
            if cookie['has_expires'] == 0:
                cookie['expires_utc'] = None
            else:
                cookie['expires_utc'] = cookie['expires_utc']/10000000

            cookies.append({'host': cookie['host_key'], 'name': cookie['name'], 'value': cookie['value'], 'path': cookie['path'], 'expires': cookie['expires_utc']})

        return libnbnotify.browser.nbCookie(cookies)


    def __del__(self):
        if self.tmp != "":
            self.socket.close()
            os.remove(self.tmp)


#b = nbBrowser()
#print b.listProfiles()
#b.load()
#print b.getCookie("facebook.com").toCookieHeader()




