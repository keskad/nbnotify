#!/usr/bin/env python
import libsubgetinstaller

class nbNotifyInstaller(libsubgetinstaller.subgetInstaller):
    localeDir = "usr/share/nbnotify/locale"
    appname = "nbnotify"

    def linuxInstall(self):
        self.osSystem("mkdir -p "+self.tmp+"/usr/bin")
        self.osSystem("cp -r ./usr "+self.tmp+"/")

        # Copy executable files
        self.osSystem("cp nbnotify.py "+self.tmp+"/usr/bin/nbnotify")

        # Make it executable
        self.osSystem("chmod +x "+self.tmp+"/usr/bin/nbnotify")

        self.compileLibraries()
        #self.compileLanguages(self.tmp)

        print("Installation done.")

    def bsdInstall(self):
        self.linuxInstall()
        print("BSD integration not supported yet.")


installer = nbNotifyInstaller()
installer.getopt()
