#-*- coding: utf-8 -*-
import libnbnotify
import BeautifulSoup
import os
import urlparse
import base64
import hashlib
import re

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'ask.fm'}

class PluginMain(libnbnotify.Plugin):
        name = "askfm"

        def _pluginInit(self):
            self.app.Hooking.connectHook("onAddPage", self.addPage)
            return True

        def addPage(self, data):
            """ Add new link from ask.fm """

            if "askfm://user/" in data['link']:
                rss = self.getPluginMethod("rss")

                internalLink = data['link']
                data['link'] = 'http://ask.fm/feed/profile/'+data['link'].replace("askfm://user/", "")+'.rss'
                data['staticPlugin'] = "rss"
                data['reallink'] = internalLink

                return rss(data)

                #return {'id': self.md5(data['link']), 'domain': 'ask.fm', 'ssl': False, 'link': '/feed/profile/'+data['link'].replace("askfm://user/", "")+'.rss', 'extension': self.getPlugin('rss')}

            if "ask.fm/" in data['link']:

                # subscribing profile notifications by cookie
                if "ask.fm/subscribe/by/cookie/" in data['link']:
                    return None

                t = re.findall("ask\.fm\/([A-Za-z0-9\_\-\@]+)", data['link'])

                if len(t) == 0:
                    self.app.Logging("Not a valid ask.fm url")
                    return None

                # this is user login
                login = t[0]

                # lets check if users exists (check if we can get user's avatar)
                validation = self.app.httpGET("ask.fm", "/"+login+"/avatar")

                if "Requested page was not found." in validation:
                    self.Logging.output("Invalid ask.fm url, user \""+login+"\" not found.", "warning", True)
                    return None

                # try to parse HTML looking for user's avatar
                try:
                    t = BeautifulSoup.BeautifulSoup(validation)
                    avatar = t.findAll("img", {"id": "nopup-picture"})
                    avatar = avatar[0]['src']
                except Exception as e:
                    self.Logging.output("Cannot validate ask.fm user \""+login+"\", HTML code parsing error "+str(e), "warning", True)
                    return None

                # create redirection to RSS plugin, so it will handle
                data['link'] = "http://ask.fm/feed/profile/"+login+".rss"
                data['icon'] = self.getAvatar(avatar)
                data['staticPlugin'] = "rss"
                data['reallink'] = "askfm://user/"+login

                obj = self.getPluginMethod("rss")
                rss = obj(data)

                if type(rss).__name__ != "dict":
                    self.app.Logging.output("RSS plugin failed on "+data['link'], "warning", True)
                    return None

                rss['reallink'] = "askfm://user/"+login
                rss['id'] = self.md5(rss['reallink'])
                rss['ssl'] = False

                self.app.Logging.output("Added "+login+" ask.fm account", "debug", False)

                #if type(rss).__name__ == "dict":
                #    self.app.setType(rss['reallink'], "rss")

                return rss
                
                

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
            return ""

            
            
