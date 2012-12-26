#-*- coding: utf-8 -*-
import libnbnotify
import BeautifulSoup
import os
import urlparse
import base64
import hashlib
import re

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Photoblog notifications parser'}

class PluginMain(libnbnotify.Plugin):
        name = "fbl"

        def _pluginInit(self):
            self.app.Hooking.connectHook("onAddPage", self.addPage)
            return True

        def addPage(self, data):
            """ To add new link add: photoblog.pl/mojphotoblog/id/{here is base64(document.cookie)} """

            if "photoblog.pl/mojphotoblog/id/" in data['link']:
                parsed = urlparse.urlparse(data['link'])
                t = parsed.path.replace("/mojphotoblog/id/", "")

                id = hashlib.md5("photoblog.pl/mojphotoblog").hexdigest()
                c = base64.b64decode(t)

                content = self.app.httpGET("www.photoblog.pl", "/mojphotoblog/?PowiadomieniaAll", cookies=c)

                if "wyloguj" in content:
                    matches = re.findall('{"uid":"([A-Za-z0-9\_\-]+)"}', content)

                    if len(matches) == 0:
                        return False

                    login = matches[0]

                    self.app.Passwords.setKey("fbl_"+login, "login", login)
                    self.app.Passwords.setKey("fbl_"+login, "key", t)
                    self.app.Passwords.save()

                    self.app.Logging.output("Catched photoblog.pl session for "+login, "debug", False)

                    return {'id': id, 'link': "/mojphotoblog/Central_powiadomienia_general.php?&photo=0&comment=1&other=0", 'extension': self, 'domain': 'www.photoblog.pl', 'cookies': c, 'reallink': "http://photoblog.pl/mojphotoblog/"+login}
                else:
                    self.app.Logging.output("photoblog session expired, please get new session to continue with link "+data['link'], "warning", True)

            elif "photoblog.pl/mojphotoblog/" in data['link']:
                id = hashlib.md5("photoblog.pl/mojphotoblog").hexdigest()

                login = data['link'].replace("http://photoblog.pl/mojphotoblog/", "")
                c = base64.b64decode(self.app.Passwords.getKey("fbl_"+login, "key"))

                return {'id': id, 'link': "/mojphotoblog/Central_powiadomienia_general.php?&photo=0&comment=1&other=0", 'extension': self, 'domain': 'www.photoblog.pl', 'cookies': c, 'reallink': "http://photoblog.pl/mojphotoblog/"+login}
                

        def _stripHTML(self, html):
            """ Remove all HTML tags and return plain text """

            soup = BeautifulSoup.BeautifulSoup(html)

            text_parts = soup.findAll(text=True)
            return ''.join(text_parts)



        def _stripSpaces(self, text):
            """ Some text fixes """

            while '  ' in text:
                text = text.replace('  ', ' ')

            try:
                text = text.replace("³", "ł")
            except Exception:
                pass
        
            return str(text.encode('utf-8'))
            
           

        def checkComments(self, pageID, data=''):
            if data == "":
                return False

            if "wylogowany." in data:
                return False

            self.app.Logging.output("photoblog notifications check for "+pageID, "debug", False)

            data = str(data)

            login = str(self.app.pages[pageID]['reallink'].replace("http://photoblog.pl/mojphotoblog/", ""))
            title = "Blog "+login+".fbl.pl"

            soup = BeautifulSoup.BeautifulSoup(data)
            elements = soup.findAll('li', {'class': 'infos_box clearfix'})

            elements.reverse()

            for element in elements:

                # i dont know its working
                if '<a href="/pro">PRO!' in str(element) or "showHideNotificationDiv" in str(element):
                    continue

                # html digging for data
                avatar = self.getAvatar(str(element.find("img", {"class": "infos_avatar"})['src']))
                profile = str(element.find("a", {"class": "infos_uidLink"})['data-uid'])
                content = str(element.find("div", {"class": "infos_content infos_thumb"}))

                t = content.split("</a>")
                content = t[len(t)-3]+"</a>"+t[len(t)-2]+"</a>" # notification content

                # who cares about someones "PRO" account? this is annoying
                if '<a href="/pro">PRO' in content:
                    continue

                content = self._stripSpaces(self._stripHTML(re.sub(r'\s', ' ', str(content))))

                id = hashlib.md5(str(content)).hexdigest()

                if not id in self.app.pages[str(pageID)]['comments']:
                    self.app.pages[str(pageID)]['title'] = title
                    self.app.pages[str(pageID)]['comments'][id] = {'username': str(profile), 'content': str(content), 'title': str(title), 'avatar': str(avatar)}
                    self.app.addCommentToDB(pageID, id, str(avatar))
                    #self.app.notifyNewData(str(content), "Blog "+login, avatar)
                    self.app.Notifications.add('fbl_'+str(login), title, content, '', avatar, pageID)

            
            
