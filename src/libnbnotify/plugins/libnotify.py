#-*- coding: utf-8 -*-
import libnbnotify
from BeautifulSoup import BeautifulSoup

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Provides Twitter.com support'}

class PluginMain(libnbnotify.Plugin):
    def _pluginInit(self):
        self.app.Hooking.connectHook("onNotifyNew", self.notifySend)
        self.app.Hooking.connectHook("onNotifyNewData", self.notifySendData)

        try:
            import pynotify
            self.notifyType = "libnotify"
            self.libnotify = pynotify
        except Exception as e:
            pass

    def notifySendData(self, a):
        data = a[0]
        title = a[1]
        #pageID = a[2]
        icon = a[3]

        if self.app.Config.get("global", "libnotify_strip_html") != False:
            data = self._stripHTML(data)

        self._libnotifySend(data, title, icon)

        return a

    def _stripHTML(self, html):
        soup = BeautifulSoup(html)

        text_parts = soup.findAll(text=True)
        return ''.join(text_parts)

    def _libnotifySend(self, message, title='', icon=''):
        try:
            self.libnotify.init("nbnotify")
            notification = self.libnotify.Notification(title, message, icon)
            notification.show()
        except Exception as e:
            print("libnotify failed, "+str(e))
