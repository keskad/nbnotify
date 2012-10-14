#-*- coding: utf-8 -*-
import libnbnotify
from BeautifulSoup import BeautifulSoup

try:
    import xmpp
except Exception:
    pass

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Jabber notifications'}

class PluginMain(libnbnotify.Plugin):
    def _pluginInit(self):
        if str(self.app.Config.getKey("libxmpp", "login")) == "False" or str(self.app.Config.getKey("libxmpp", "password")) == "False" or str(self.app.Config.getKey("libxmpp", "client_jid")) == "False":
            self.app.Logging.output("Jabber notifications disabled because of no login details. Example configuration:\n[libxmpp] login=server@login.com\npassword=yourpassword\nclient_jid = your@jid.org", "debug", False)
            return False

        xmpp # exception should disable the plugin

        self.app.Hooking.connectHook("onNotifyNew", self.notifySend)
        self.app.Hooking.connectHook("onNotifyNewData", self.notifySendData)

        try:
            jid = xmpp.protocol.JID(self.app.Config.getKey("libxmpp", "login"))
            self.xmpp = xmpp.Client(jid.getDomain(), debug=[])
            self.xmpp.connect()
            self.xmpp.auth(jid.getNode(), self.app.Config.getKey("libxmpp", "password"))
        except Exception as e:
            self.app.Logging.output("Cannot connect to XMPP server, please check configuration. "+str(e), "warning", True)

    def notifySendData(self, a):
        data = a[0]
        title = a[1]
        #pageID = a[2]
        icon = a[3]

        self._libnotifySend(data, title, icon)

        return a


    def notifySend(self, a):
        pageID = str(a[0])
        id = str(a[1].encode("utf-8"))

        # a[2] - template
        content = str(a[2].encode("utf-8")).replace("%username%", str(self.app.pages[pageID]['comments'][id]['username'].encode("utf-8"))).replace("%title%", str(self.app.pages[pageID]['title'].encode("utf-8")).replace("\n", ""))

        self.xmpp.send(xmpp.protocol.Message("webnull@ubuntu.pl", content+"\n\n"+self._stripHTML(self.app.pages[pageID]['comments'][id]['content'].replace("<br/>", "\n"))))

        #os.system('/usr/bin/notify-send "<b>'+self.shellquote(self.pages[pageID]['comments'][id]['username'])+'</b> skomentował wpis '+self.shellquote(self.pages[pageID]['title'].replace("!", "."))+':" \"'+self.shellquote(self.pages[pageID]['comments'][id]['content']).replace("!", ".")+'\" -i '+self.self.pages[pageID]['comments'][id]['avatar']+' -u low -a dpnotify')

        return a

    def _stripHTML(self, html):
        soup = BeautifulSoup(html)

        text_parts = soup.findAll(text=True)
        return ''.join(text_parts)

    def _libnotifySend(self, message, title='', icon=''):
        try:
            self.xmpp.send(xmpp.protocol.Message(str(self.app.Config.getKey("libxmpp", "client_jid")), "## "+str(title.encode("utf-8"))+": \n"+str(message.encode("utf-8"))))
        except Exception as e:
            self.app.Logging.output("Cannot send message to "+str(self.app.Config.getKey("libxmpp", "client_jid"))+", "+str(e), "debug", False)



