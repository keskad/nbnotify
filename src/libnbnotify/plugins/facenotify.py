#-*- coding: utf-8 -*-
import libnbnotify
import BeautifulSoup
import hashlib
import os
import httplib
import urllib
import urlparse
import re
import json
#import time

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Facebook notifications'}

class PluginMain(libnbnotify.Plugin):
        name = "facenotify"

        def _pluginInit(self):
            self.app.Hooking.connectHook("onAddPage", self.addPage)
            self.app.Hooking.connectHook("onAddService", self.addService)
            return True


        def addService(self, data):
            if data['service'] == "facebook":
                browser = data['browser']
                cookies = browser.getCookie("facebook.com").toCookieHeader()
                
                if cookies != "":
                    # https://www.facebook.com/notifications

                    headers = dict()
                    headers['accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                    headers['accept-charset'] = 'ISO-8859-2,utf-8;q=0.7,*;q=0.3'
                    #headers['accept-encoding'] = '
                    headers['accept-language'] = 'en-US,en;q=0.8,pl;q=0.6'
                    headers['cookie'] = cookies
                    headers['dnt'] = '1'
                    headers['host'] = 'www.facebook.com'
                    headers['method'] = 'GET'
                    headers['referer'] = 'https://www.facebook.com/home.php'
                    headers['scheme'] = 'https'
                    headers['version'] = 'HTTP/1.1'
                    headers['user-agent'] = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1312.52 Safari/537.17'
                    headers['url'] = '/notifications'

                    contents = self.app.httpGET('www.facebook.com', '/notifications', secure=True, cookies=cookies, headers=headers)

                    r = re.findall("\/feeds\/notifications\.php\?([A-Za-z\&\;0-9\=\_\-\.]+)\"\>", contents)

                    if len(r) > 0:
                        link = "https://www.facebook.com/feeds/notifications.php?"+urllib.unquote(r[0].replace('&amp;', '&'))

                    return {'link': link}

                return False



        def addPage(self, data):
            if data['link'][0:48] == 'https://www.facebook.com/feeds/notifications.php':
                url = urlparse.urlparse(data['link'])
                tmp = self.app.httpGET("www.facebook.com", "/feeds/notifications.php?"+url.query)

                if "SyndicationErrorFeed" in tmp:
                    self.app.Logging.output("Facebook syndication link expired, please visit https://www.facebook.com/notifications to get new valid one", "warning", True)
                    return False

                # get information about user session
                face_uid = re.findall("id=([0-9]+)", url.query)

                if len(face_uid) == 0:
                    self.app.Logging.output("Invalid facebook link, missing one of required parametrs", "warning", False)
                    return False

                try:
                    userInfo = json.loads(self.app.httpGET("graph.facebook.com", "/"+face_uid[0]))
                    self.app.Logging.output("Catched facebook syndication link for userid: "+userInfo['name'], "debug", False)
                except Exception as e:
                    self.app.Logging.output("Cannot get user informations from Facebook API, "+str(e), "warning", True)
                    self.app.Logging.output("Catched facebook syndication link for unknown user", "debug", False)
                
                return {'id': id, 'link': "/feeds/notifications.php?"+url.query, 'extension': self, 'domain': url.netloc, 'ssl': True}

        def checkComments(self, pageID, data=''):
            if data == "":
                return False

            soup = BeautifulSoup.BeautifulStoneSoup(data)
            items = soup.findAll('item')
            domain = "www.facebook.com"
            localAvatar = ""

            a = self.app.configGetKey("rssicons", pageID)
            if str(a) != "False":
                localAvatar = a

            items.reverse()
            i = 0

            for item in items:
                i = i + 1

                if i > self.app.Notifications.maxMessagesPerEvent:
                    break


                content = item.find("description").string
                title = item.find("title").string
                
                localAvatar = ""

                # try to get any image from content to display as notification icon
                if "<img src" in content and str(a) == "False":
                    try:
                        t = BeautifulSoup.BeautifulSoup(content)
                        t = t.findAll("img")
                        localAvatar = self.getAvatar(t[0]['src'])
                    except Exception:
                        localAvatar = ""
                        pass

                # get avatar from facebook graph api
                try:
                    t = BeautifulSoup.BeautifulSoup(content)
                    a = t.findAll("a")

                    if len(a) > 0:
                        for k in a:
                            k['href'] = k['href'].replace("%2F", "/")

                            if "/n/?photo.php" in k['href']:
                                continue

                            if "/n/?pages/" in k['href']:
                                test = re.findall("n\/\?pages\/([A-Za-z0-9\-\_]+)\/([0-9]+)", k['href'])

                                if len(test) > 0:
                                    localAvatar = self.getAvatar("http://graph.facebook.com/"+test[0][1]+"/picture", imgType="jpg", cacheLifeTime=172800)
                                break

                            if "https://www.facebook.com/n/?" in k['href']:
                                test = re.findall("n/\?([A-Za-z0-9\.\_\-]+)&", k['href'])

                                if test[0] == 'profile.php':
                                    test = re.findall("id=([0-9]+)", k['href'])

                                if len(test) > 0:
                                    localAvatar = self.getAvatar("http://graph.facebook.com/"+test[0]+"/picture", imgType="jpg", cacheLifeTime=86400)

                                break



                except Exception as e:
                    self.app.Logging.output("Cannot parse facebook notification photo, "+str(e), "warning", True)
                    pass

                #date = int(time.time())

                # exists(self, title, content, pageID, salt=''):
                # add(self, eventName, title, content, date, icon='', pageID='', salt='', testMode=False):

                sid = hashlib.md5(title).hexdigest()

                if self.app.Notifications.exists(sid) == False:
                    self.app.Notifications.add('facenotify', 'Facebook', content, '', icon=localAvatar, pageID=pageID, sid=sid)






