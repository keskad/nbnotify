#-*- coding: utf-8 -*-
import libnbnotify
import BeautifulSoup
import hashlib
import os
import httplib
import urlparse
import re
import json

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Facebook notifications'}

class PluginMain(libnbnotify.Plugin):
        name = "facenotify"

        def _pluginInit(self):
            self.app.Hooking.connectHook("onAddPage", self.addPage)
            return True

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
            domain = urlparse.urlparse(soup.find("link").string).hostname
            localAvatar = ""

            a = self.app.configGetKey("rssicons", pageID)
            if str(a) != "False":
                localAvatar = a

            items.reverse()

            for item in items:
                title = item.find("title").string
                content = item.find("description").string
                
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

                            if "/n/?pages/" in k['href']: # /n/?pages/I-hate-like-share-or-comment-spam-on-fb/
                                test = re.findall("n\/\?pages\/([A-Za-z0-9\-\_]+)\/([0-9]+)", k['href'])

                                if len(test) > 0:
                                    localAvatar = self.getAvatar("http://graph.facebook.com/"+test[0][1]+"/picture", imgType="jpg")
                                break

                            if "http://www.facebook.com/n/?" in k['href']:
                                test = re.findall("n/\?([A-Za-z0-9\.\_\-]+)&", k['href'])

                                if test[0] == 'profile.php':
                                    test = re.findall("id=([0-9]+)", k['href'])

                                if len(test) > 0:
                                    localAvatar = self.getAvatar("http://graph.facebook.com/"+test[0]+"/picture", imgType="jpg")

                                break



                except Exception as e:
                    self.app.Logging.output("Cannot parse facebook notification photo, "+str(e), "warning", True)
                    pass

                id = hashlib.md5(title).hexdigest()

                if not id in self.app.pages[str(pageID)]['comments']:
                    self.app.pages[str(pageID)]['title'] = title
                    self.app.pages[str(pageID)]['comments'][id] = {'username': domain, 'content': content, 'title': title, 'avatar': localAvatar}
                    self.app.addCommentToDB(pageID, id, localAvatar)
                    #self.app.notifyNew(pageID, id, "\"%title%\"")
                    self.app.Notifications.add('facenotify', 'Facebook', content, '', localAvatar, pageID='')
