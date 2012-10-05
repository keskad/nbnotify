#-*- coding: utf-8 -*-
from PyQt4 import QtCore, QtGui, QtWebKit, QtNetwork
import libnbnotify
import sys
import BeautifulSoup

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Provides notifications throught QT interface'}

class PluginMain(libnbnotify.Plugin):
    notifier = None

    def _pluginInit(self):
        app = QtGui.QApplication(sys.argv)
        #self.app.Hooking.connectHook("onNotifyNew", self.notifySend)
        #self.app.Hooking.connectHook("onNotifyNewData", self.notifySendData)

        iconFile = "/usr/share/nbnotify/icon.jpg"
        icon = QtGui.QIcon(iconFile)
        self.notifier = QtGui.QSystemTrayIcon(icon)
        self.notifier.show()

        self.notifySendData(['this is a teeeest', 'example of title', 'icon is not important', 'icon'])


    def notifySendData(self, a):
        data = a[0]
        title = a[1]
        #pageID = a[2]
        icon = a[3]

        self._libnotifySend(data, title, icon)

        return a


    def notifySend(self, a):
        print a

        pageID = a[0]
        id = a[1]

        # a[2] - template
        content = a[2].replace("%username%", self.app.pages[pageID]['comments'][id]['username']).replace("%title%", self.app.pages[pageID]['title'].replace("\n", ""))

        # it's the same thing like a commented line below
        self._libnotifySend(self._stripHTML(self.app.pages[pageID]['comments'][id]['content'].replace("<br/>", "\n")), content, self.app.pages[pageID]['comments'][id]['avatar'])

        return a

        #os.system('/usr/bin/notify-send "<b>'+self.shellquote(self.pages[pageID]['comments'][id]['username'])+'</b> skomentował wpis '+self.shellquote(self.pages[pageID]['title'].replace("!", "."))+':" \"'+self.shellquote(self.pages[pageID]['comments'][id]['content']).replace("!", ".")+'\" -i '+self.self.pages[pageID]['comments'][id]['avatar']+' -u low -a dpnotify')

    def _stripHTML(self, html):
        soup = BeautifulSoup(html)

        text_parts = soup.findAll(text=True)
        return ''.join(text_parts)

    def _libnotifySend(self, message, title='', iconFile=''):
        try:
            self.notifier.showMessage(title, message, 20000)
        except Exception as e:
            print("qtnotify failed, "+str(e))
