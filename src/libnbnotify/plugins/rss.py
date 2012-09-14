#-*- coding: utf-8 -*-
import libnbnotify
import BeautifulSoup
import hashlib
import os
import httplib
import urlparse

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Provides support for blogs on dobreprogramy.pl'}

class PluginMain(libnbnotify.Plugin):
        name = "rss"

        def _pluginInit(self):
            self.app.Hooking.connectHook("onAddPage", self.addPage)
            return True

        def addPage(self, data):
            # this plugin works only if link has specified static plugin
            if data['staticPlugin'] == self.name:
                domain = urlparse.urlparse(data['link']).hostname
                link = data['link'].replace("http://"+domain, "")
                id = "rss_"+hashlib.md5(data['link']).hexdigest()

                # icon file
                a = self.app.configGetKey("rssicons", id)
                if str(a) == "False":
                    self.Logging.output("No icon file found for this RSS resource, use nbnotify --force-new --config=rssicons:"+str(id)+" --value=path-to-icon-file to set icon file", "debug", False)

                return {'id': id, 'link': link, 'extension': self, 'domain': domain}

        def checkComments(self, pageID, data=''):
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

                id = hashlib.md5(title).hexdigest()

                if not id in self.app.pages[str(pageID)]['comments']:
                    self.app.pages[str(pageID)]['title'] = title
                    self.app.pages[str(pageID)]['comments'][id] = {'username': domain, 'content': content, 'title': title, 'avatar': localAvatar}
                    self.app.addCommentToDB(pageID, id, localAvatar)
                    self.app.notifyNew(pageID, id, "\"%title%\"")
