#-*- coding: utf-8 -*-
import libnbnotify
import BeautifulSoup
import hashlib
import os
import httplib
import urlparse

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Provides simple RSS handler'}

class PluginMain(libnbnotify.Plugin):
        name = "rss"

        def _pluginInit(self):
            self.app.Hooking.connectHook("onAddPage", self.addPage)
            return True

        def addPage(self, data):
            # this plugin works only if link has specified static plugin
            if data['staticPlugin'] == self.name:
                domain = urlparse.urlparse(data['link']).hostname
                link = data['link'].replace("http://"+domain, "").replace("https://"+domain, "")
                id = "rss_"+hashlib.md5(data['link']).hexdigest()
                fixedUrl = self.app.configGetKey("rss_fixurl", id)

                ##### HANDLING 301 MOVED
                if fixedUrl != "True":
                    self.Logging.output("Checking RSS url and trying to fix domain/location if got 301 MOVED")

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
                

                # icon file
                a = self.app.configGetKey("rssicons", id)
                if str(a) == "False":
                    self.Logging.output("No icon file found for this RSS resource, use nbnotify --force-new --config=rssicons:"+str(id)+" --value=path-to-icon-file to set icon file", "debug", False)

                return {'id': id, 'link': link, 'extension': self, 'domain': domain, 'ssl': True}

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

            for item in items:
                title = item.find("title").string
                content = item.find("description").string

                # try to get any image from content to display as notification icon
                if "<img src" in content and str(a) == "False":
                    try:
                        t = BeautifulSoup.BeautifulSoup(content)
                        t = t.findAll("img")
                        localAvatar = self.getAvatar(t[0]['src'])
                    except Exception:
                        localAvatar = ""
                        pass

                id = hashlib.md5(title).hexdigest()

                if not id in self.app.pages[str(pageID)]['comments']:
                    self.app.pages[str(pageID)]['title'] = title
                    self.app.pages[str(pageID)]['comments'][id] = {'username': domain, 'content': content, 'title': title, 'avatar': localAvatar}
                    self.app.addCommentToDB(pageID, id, localAvatar)
                    self.app.notifyNew(pageID, id, "\"%title%\"")
