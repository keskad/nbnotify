#-*- coding: utf-8 -*-
import libnbnotify
import os
import subprocess

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Sound support'}

class PluginMain(libnbnotify.Plugin):
        """ This plugin is adding sound notifications to nbnotify """

        _sound = None
        _file = '/usr/share/sounds/question.wav'
        enabled = True

        def _pluginInit(self):
            """ Initialize plugin, check if sound is enabled in config """

            if str(self.app.Config.getKey("global", "sound")) == "False":
                self.enabled = False
                self.app.Logging.output("To enable sound set global->sound to True", "debug", False)
                return False

            if not os.path.isfile(self._file):
                self.app.Logging.output("Cannot find sound file \""+self._file+"\"", "warning", True)
                return False

            self.app.Hooking.connectHook("onSendMessages", self.soundNotify)

            # check if pyglet is installed
            try:
                import pyglet
                sound = pyglet.media.load(self._file, streaming=False)
            except Exception as e:
                pass

            return True

        def soundNotify(self, count=''):
            """ Play sound notifications """

            if os.path.isfile(str(self.app.Config.getKey("global", "soundfile"))):
                self._file = self.app.Config.getKey("global", "soundfile")

            if not os.path.isfile(self._file):
                self.app.Logging.output("Cannot find sound file \""+self._file+"\"", "warning", True)
                return False

            # pyglet
            if self._sound != None:
                self._sound.play()
                return count

            # mplayer
            if os.path.isfile("/usr/bin/mplayer"):
                subprocess.call(["mplayer", self._file, "-quiet"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)           
                return count

            # sox
            if os.path.isfile("/usr/bin/play"):
                subprocess.call(["play", self._file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return count      

            self.app.Logging.output("Cannot find pyglet library, mplayer and sox. Cant play notification sound.", "warning", True)
            return count

