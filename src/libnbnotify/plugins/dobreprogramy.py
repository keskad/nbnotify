#-*- coding: utf-8 -*-
import libnbnotify
import re
import BeautifulSoup
import hashlib
import os
import httplib

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Provides support for blogs on dobreprogramy.pl'}

class PluginMain(libnbnotify.Plugin):
        def _pluginInit(self):
            self.app.Hooking.connectHook("onAddPage", self.addPage)
            return True

        def addPage(self, data):
            link = data['link']

            if not "dobreprogramy.pl" in link:
                return False

            link = link.replace("http://www.dobreprogramy.pl/", "").replace("http://dobreprogramy.pl", "").replace("dobreprogramy.pl", "").replace("www.dobreprogramy.pl", "")

            # RSS channel
            match = re.findall("([A-Za-z0-9_\-\@ĄąŻżĘęŹźÓóŁł\$\#\&\;]+),Rss", link)

            if len(match) > 0:
                match[0] = "rss_"+match[0]
                self.Logging.output("Found RSS at "+match[0], "debug", False)
            else:
                # match for blog entry
                match = re.findall(",([0-9]+).html", link)
            

            if len(match) == 0:
                self.Logging.output("Invalid dobreprogramy.pl link format.")
                return False

            if str(match[0]) in self.app.pages:
                return False

            return {'id': "dp_"+str(match[0]), 'link': link, 'extension': self, 'domain': 'www.dobreprogramy.pl'}

        def downloadAvatar(self, avatar, fromHTML=False):
            """ Download avatar to local cache """

            m = hashlib.md5(avatar).hexdigest()
            icon = self.app.iconCacheDir+"/"+m+".png"

            if not os.path.isfile(icon):
                # getting avatar from profile page
                if fromHTML == True:
                    userName = avatar.replace(",Rss", "")
                    self.Logging.output("GET: dobreprogramy.pl/"+userName, "debug", False)

                    data = self.app.httpGET("www.dobreprogramy.pl", "/"+userName)

                    if data == False:
                        self.Logging.output("Cannot get avatar link, connection problem.", "warning", True)
                        return "" # Return always same type like in C (string)

                    # <img src="http://avatars.dpcdn.pl/Avatar.ashx?file=140049_1346504879.png&amp;type=UGCUserInfo" width="140" heigh="140" alt="avatar">
                    soup = BeautifulSoup.BeautifulSoup(data)

                    try:
                        element = soup.find("img", alt="avatar")
                        avatar = element['src'] 
                    except Exception as e:
                        self.Logging.output("Something went wrong parsing HTML code to get avatar link, maybe dobreprogramy.pl has changed something?", "warning", True)
                        return ""

                url = avatar.replace("http://avatars.dpcdn.pl", "").replace("http://www.avatars.dpcdn.pl", "").replace("www.avatars.dpcdn.pl", "").replace("avatars.dpcdn.pl", "")
                data = self.app.httpGET("avatars.dpcdn.pl", url)

                if data == False:
                    self.Logging.output("Cannot download avatar file, url=avatars.dpcdn.pl/"+url, "warning", True)
                    return ""
                else:
                    w = open(icon, "wb")
                    w.write(data)
                    w.close()
                    self.Logging.output("Avatar saved: avatars.dpcdn.pl/"+url, "debug", False)
                
            return icon

        def checkRSS(self, pageID, data):
            soup = BeautifulSoup.BeautifulStoneSoup(data)
            items = soup.findAll('item')
            isNew = False

            for item in items:
                title = str(item.find("title").string)
                author = str(item.find("author").string)
                content = str(item.find("description").string)

                id = hashlib.md5(str(title)).hexdigest()

                if not id in self.app.pages[str(pageID)]['comments']:
                    isNew = True

                localAvatar = self.downloadAvatar(author, fromHTML=True)
                self.app.pages[str(pageID)]['title'] = title
                self.app.pages[str(pageID)]['comments'][id] = {'avatar': localAvatar}
                self.app.pages[str(pageID)]['comments'][id]['username'] = author
                self.app.pages[str(pageID)]['comments'][id]['content'] = content

                if isNew == True:
                    self.app.addCommentToDB(pageID, id, localAvatar)
                    self.app.notifyNew(pageID, id, "%username% utworzył wpis \"%title%\"")
                    isNew = False
                

            return True
            

        def checkComments(self, pageID, data=''):
            """ Parse all comments """

            if self.app.pages[pageID]['id'][0:6] == "dp_rss":
                return self.checkRSS(pageID, data)

            soup = BeautifulSoup.BeautifulSoup(data)

			# the title is too long, so we cut it a little bit
            self.app.pages[pageID]['title'] = str(soup.html.head.title.string).replace("- blogi użytkowników portalu dobreprogramy", "")
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
                    self.app.notifyNew(pageID, id, "%username% skomentował wpis \"%title%\"")
                    self.app.addCommentToDB(pageID, id, localAvatar)
                    isNew = False
