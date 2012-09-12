import libnbnotify
import re
import BeautifulSoup
import hashlib
import os

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Provides support for blogs on dobreprogramy.pl'}

class PluginMain(libnbnotify.Plugin):
        def _pluginInit(self):
            self.app.Hooking.connectHook("onAddPage", self.addPage)
            return True

        def addPage(self, link):
            if not "dobreprogramy.pl" in link:
                return False

            link = link.replace("http://www.dobreprogramy.pl/", "").replace("http://dobreprogramy.pl", "").replace("dobreprogramy.pl", "").replace("www.dobreprogramy.pl", "")
            match = re.findall(",([0-9]+).html", link)

            if len(match) == 0:
                self.Logging.output("Invalid dobreprogramy.pl link format.")
                return False

            if str(match[0]) in self.app.pages:
                return False

            return {'id': str(match[0]), 'link': link, 'extension': self, 'domain': 'www.dobreprogramy.pl'}

        def downloadAvatar(self, avatar):
            """ Download avatar to local cache """

            m = hashlib.md5(avatar).hexdigest()
            icon = self.app.iconCacheDir+"/"+m+".png"

            if not os.path.isfile(icon):
                url = avatar.replace("http://avatars.dpcdn.pl", "").replace("http://www.avatars.dpcdn.pl", "").replace("www.avatars.dpcdn.pl", "").replace("avatars.dpcdn.pl", "")

                connection = httplib.HTTPConnection("avatars.dpcdn.pl", 80, timeout=int(self.configGetKey("connection", "timeout")))
                connection.request("GET", url)
                response = connection.getresponse()
                data = response.read()
                connection.close()

                w = open(icon, "wb")
                w.write(data)
                w.close()
                self.Logging.output("GET: avatars.dpcdn.pl/"+url, "debug", False)
                
            return icon

        def checkComments(self, pageID, data=''):
            """ Parse all comments """

            soup = BeautifulSoup.BeautifulSoup(data)

            self.app.pages[pageID]['title'] = str(soup.html.head.title.string)
            commentsHTML = soup.findAll('div', {'class': "odd item"})
            commentsEven = soup.findAll('div', {'class': "even item"})
            commentsHTML = commentsHTML+commentsEven

            isNew = False
            commentsList = dict()

            for comment in commentsHTML:
                # comment id - first <img src="(.*)"
                cSoup = BeautifulSoup.BeautifulSoup(str(comment))
                id = str(cSoup.div['id'])

                if not id in self.app.pages[str(pageID)]['comments']:
                    isNew = True

                avatar = str(cSoup.img['src'])
                localAvatar = self.downloadAvatar(avatar)
                self.app.pages[str(pageID)]['comments'][id] = {'avatar': localAvatar}

                # user name - <a class="color-inverse"
                cInv = cSoup.findAll("a", {'class': 'color-inverse'})

                # guests users
                if len(cInv) == 0: 
                    cInv = cSoup.findAll("span")
                    nSoup = BeautifulSoup.BeautifulSoup(str(cInv[0]))
                    self.app.pages[str(pageID)]['comments'][id]['username'] = str(nSoup.span.string)

                else:
                    nSoup = BeautifulSoup.BeautifulSoup(str(cInv[0]))
                    self.app.pages[str(pageID)]['comments'][id]['username'] = str(nSoup.a.string)

                # comment content - <div class="text-h75 tresc"
                nSoup = str(cSoup.findAll("div", {'class': "text-h75 tresc"})[0]).replace('<div class="text-h75 tresc">', '').replace('</div>', '')
                self.app.pages[str(pageID)]['comments'][id]['content'] = nSoup
               # self.pages[str(pageID)]['comments'][id]['content'] = 

                if isNew == True:
                    self.app.notifyNew(pageID, id)
                    self.app.addCommentToDB(pageID, id, localAvatar)
                    isNew = False
