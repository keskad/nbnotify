import libnbnotify

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Provides Twitter.com support'}

class PluginMain(libnbnotify.Plugin):
        def _pluginInit(self):
            return True
