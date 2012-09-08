#-*- coding: utf-8 -*-
import libnbnotify

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Provides Twitter.com support'}

class PluginMain(libnbnotify.Plugin):
    def _pluginInit(self):
        self.app.Hooking.connectHook("onNotifyNew", self.notifySend)

        try:
            import pynotify
            self.notifyType = "libnotify"
            self.libnotify = pynotify
        except Exception as e:
            pass


    def notifySend(self, a):
        pageID = a[0]
        id = a[1]

        self._libnotifySend(self.app.pages[pageID]['comments'][id]['content'], "\"<b>"+self.app.pages[pageID]['comments'][id]['username']+"</b>\" skomentował wpis "+self.app.pages[pageID]['title']+":", self.app.pages[pageID]['comments'][id]['avatar'])

        #os.system('/usr/bin/notify-send "<b>'+self.shellquote(self.pages[pageID]['comments'][id]['username'])+'</b> skomentował wpis '+self.shellquote(self.pages[pageID]['title'].replace("!", "."))+':" \"'+self.shellquote(self.pages[pageID]['comments'][id]['content']).replace("!", ".")+'\" -i '+self.self.pages[pageID]['comments'][id]['avatar']+' -u low -a dpnotify')


    def _libnotifySend(self, message, title='', icon=''):
        try:
            self.libnotify.init("nbnotify")
            notification = self.libnotify.Notification(title, message, icon)
            notification.show()
        except Exception as e:
            print("libnotify failed, "+str(e))
