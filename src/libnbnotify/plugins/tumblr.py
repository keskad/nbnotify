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

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'lnxmen', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Tumblr notifications'}

class PluginMain(libnbnotify.Plugin):
        name = "tumblr"

        def _pluginInit(self):
            self.app.Hooking.connectHook("onAddPage", self.addPage)
            return True

        def addPage(self, data):
            if data['staticPlugin'] == self.name:
                domain = urlparse.urlparse(data['link']).hostname
                link = data['link'].replace("http://"+domain, "").replace("https://"+domain, "")

                if "reallink" in data:
                    id = hashlib.md5(data['reallink']).hexdigest()
                   
                else:
                    id = hashlib.md5(domain).hexdigest()
        
                fixedUrl = self.app.configGetKey("rss_fixurl", id)

                ##### HANDLING 301 MOVED
                if fixedUrl != "True":
                    self.Logging.output("Checking RSS url and trying to fix domain/location if got 301 MOVED, "+domain+link)

                    try:
                        connection = httplib.HTTPConnection(domain, 80, timeout=int(self.app.configGetKey("connection", "timeout")))
                        connection.request("GET", link, headers=self.app.headers)
                        response = connection.getresponse()

                        if str(response.status) != "200":
                            if str(response.status) != "301":
                                self.Logging.output("Got "+str(response.status)+", cannot parse link.")
                                return False

                            headers = response.getheaders()
                            for header in headers:
                                if header[0] == "location":
                                    parsedurl = urlparse.urlparse(header[1])
                                    domain = parsedurl.netloc # move to other domain
                                    link = parsedurl.path # move to other path

                                    # ?a=b&c=d
                                    if parsedurl.query != "":
                                        link += link+"?"+parsedurl.query

                                    self.app.configSetKey("rss_fixurl", id, header[1])
                                    self.app.saveConfiguration()
                        else:
                            self.app.configSetKey("rss_fixurl", id, "Correct")
                            self.app.saveConfiguration()
                    except Exception as e:
                        self.Logging.output("Received exception while trying to check url, "+str(e))
                        return False
                else:
                    if fixedUrl != "Correct":
                        url = urlparse.urlparse(data['link'])
                        domain = url.netloc
                        link = url.path

                        # ?a=b&c=d
                        if url.query != "":
                            link += link+"?"+url.query

                #### END OF 301 MOVED HANDLER
                
                return {'id': id, 'link': link, 'extension': self, 'domain': domain, 'ssl': True}

        def checkComments(self, pageID, data=''):
            if data == "":
                return False

            soup = BeautifulSoup.BeautifulStoneSoup(data)
            items = soup.findAll('item')
            domain = urlparse.urlparse(soup.find("link").string).hostname
            
            title = domain.split('.')[0]

            postImage = ""
            items.reverse()
            i = 0

            for item in items:
                i = i + 1

                if i > self.app.Notifications.maxMessagesPerEvent and self.app.Notifications.maxMessagesPerEvent > 0:
                    break

                content = item.find("description").string
                content = content.replace('&lt;', '<').replace('&gt;', '>')

                # try to get any image from content to display as notification icon
                if "<img src" in content:
                    try:
                        t = BeautifulSoup.BeautifulSoup(content)
                        t = t.findAll("img")
                        
                        if t[0]['src'][-3:] != 'jpg' and t[0]['src'][-3:] != 'png':
                            return False
                        
                        imageLink = t[0]['src'].replace('_500', '_100')
                        
                        postImage = self.getAvatar(imageLink)
                    except Exception:
                        postImage = ""
                        pass
                else:
                    return False

                sid = hashlib.md5('tumblr_'+title+"_"+imageLink.split('/')[-1]).hexdigest()

                if self.app.Notifications.exists(sid) == False:
                    print(postImage)
                    self.app.Notifications.add('tumblr_'+pageID, 'Tumblr', title.title()+' has been added new post!', '', postImage, pageID, sid=sid)
