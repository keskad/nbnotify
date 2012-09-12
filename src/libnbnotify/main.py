#-*- coding: utf-8 -*-
import libnbnotify
import traceback
import os, hashlib, re, BeautifulSoup, sys, time, glob, traceback
from distutils.sysconfig import get_python_lib
from StringIO import StringIO

if sys.version_info[0] >= 3:
    import configparser
    import http.client as httplib
    import io as StringIO
else:
    import StringIO
    import ConfigParser as configparser
    import httplib


class nbnotify:
    Config = dict()
    #Config['connection'] = dict()
    #Config['connection']['timeout'] = 5 # 5 seconds
    iconCacheDir = os.path.expanduser("~/.nbnotify/cache")
    configDir = os.path.expanduser("~/.nbnotify")
    configTime = None # config last modification time
    db = None
    pages = dict()
    Hooking = libnbnotify.Hooking()

    # Plugin system adapted from Subget
    disabledPlugins = list()
    plugins=dict()
    pluginsList=list() # ordered list

    def __init__(self):
        self.Logging = libnbnotify.Logging(self)

    def shellquote(self, s):
        return "'" + s.replace("'", "'\\''") + "'"

    def configSetKey(self, Section, Option, Value):
        if not Section in self.Config:
            self.Config[Section] = dict()

        self.Config[Section][Option] = str(Value)

    def saveConfiguration(self):
        Output = ""

        # saving settings to file
        for Section in self.Config:
            Output += "["+str(Section)+"]\n"

            for Option in self.Config[Section]:
                Output += str(Option)+" = "+str(self.Config[Section][Option])+"\n"

            Output += "\n"

        try:
            self.Logging.output("Saving to "+self.configDir+"/config", "debug", True)
            Handler = open(self.configDir+"/config", "wb")
            Handler.write(Output)
            Handler.close()
        except Exception as e:
            print("Cannot save configuration to file "+self.configDir+"/config")

        self.configTime = os.path.getmtime(self.configDir+"/config")

    def loadConfig(self):
        """ Parsing configuration ini file """

        if not os.path.isdir(self.configDir):
            try:
                os.mkdir(self.configDir)
            except Exception:
                print("Cannot create "+self.configDir+" directory, please check your permissions")

        configPath = os.path.expanduser(self.configDir+"/config")

        if not os.path.isfile(configPath):
            w = open(configPath, "w")
            w.write("[connection]\ntimeout = 60\n\n[global]\nchecktime = 60")
            w.close()

        if os.path.isfile(configPath):
            Parser = configparser.ConfigParser()
            try:
                Parser.read(configPath)
            except Exception as e:
                self.Logging.output("Error parsing configuration file from "+self.configDir+"/config, error: "+str(e), "critical", True)
                sys.exit(os.EX_CONFIG)

            # all configuration sections
            Sections = Parser.sections()

            for Section in Sections:
                Options = Parser.options(Section)
                self.Config[Section] = dict()

                # and configuration variables inside of sections
                for Option in Options:
                    self.Config[Section][Option] = Parser.get(Section, Option)

        self.configTime = os.path.getmtime(self.configDir+"/config")

    def configGetSection(self, Section):
        """ Returns section as dictionary 

            Args:
              Section - name of section of ini file ([section] header)

            Returns:
              Dictionary - on success
              False - on false

        """
        return self.Config.get(Section, False)

    def configGetKey(self, Section, Key):
        """ Returns value of Section->Value configuration variable

            Args:
              Section - name of section of ini file ([section] header)
              Key - variable name

            Returns:
              False - when section or key does not exists
              False - when value of variable is "false" or "False" or just False
              string value - value of variable
        """
        try:
            cfg = self.Config[Section][Key]
            if str(cfg).lower() == "false":
                return False
            else:
                return cfg
        except KeyError:
            return False

    def downloadPage(self, pageID):
        """ Download page and check md5 sum """

        connection = httplib.HTTPConnection(self.pages[pageID]['domain'], 80, timeout=int(self.configGetKey("connection", "timeout")))
        connection.request("GET", "/"+str(self.pages[pageID]['link']))
        response = connection.getresponse()
        data = response.read()
        self.Logging.output("GET: "+self.pages[pageID]['domain']+"/"+self.pages[pageID]['link'], "debug", False)
        connection.close()
        return data

    def checkSum(self, data, pageID):
        # check md5 sums
        m = hashlib.md5(data).digest()

        if m == self.pages[pageID]['hash']:
            return True

        self.pages[pageID]['hash'] = m
        return False

    def addPage(self, link):
        data = self.Hooking.executeHooks(self.Hooking.getAllHooks("onAddPage"), link)

        if type(data).__name__ == "dict":
            try:
                self.pages[str(data['id'])] = {'hash': '', 'link': data['link'], 'comments': dict(), 'extension': data['extension'], 'domain': data['domain']}
                self.Logging.output("Adding "+link, "", False)
            except Exception as e:
                buffer = StringIO()
                traceback.print_exc(file=buffer)
                self.Logging.output("Cannot add "+link+", exception: "+str(buffer.getvalue()), "warning", True, skipDate=True)

        else:
            self.Logging.output("No any suitable extension supporting link format \""+link+"\" found", "warning", True)
            return False

    def addCommentToDB(self, pageid, id, localAvatar):
        try:
            self.db.cursor.execute("INSERT INTO `comments` (page_id, comment_id, content, username, avatar) VALUES (?, ?, ?, ?, ?)", (str(pageID), str(id), str(self.pages[str(pageID)]['comments'][id]['content']), str(self.pages[str(pageID)]['comments'][id]['username']), str(localAvatar)))
        except sqlite3.IntegrityError:
            pass # sqlite3.IntegrityError: column comment_id is not unique


    def notifyNew(self, pageID, id):
        self.Hooking.executeHooks(self.Hooking.getAllHooks("onNotifyNew"), [pageID, id])
        #os.system('/usr/bin/notify-send "<b>'+self.shellquote(self.pages[pageID]['comments'][id]['username'])+'</b> skomentował wpis '+self.shellquote(self.pages[pageID]['title'].replace("!", "."))+':" \"'+self.shellquote(self.pages[pageID]['comments'][id]['content']).replace("!", ".")+'\" -i '+self.self.pages[pageID]['comments'][id]['avatar']+' -u low -a dpnotify')


    def checkComments(self, pageID, data=''):
        """ Parse all comments """

        try:
            extension = self.pages[pageID]['extension']
            extension.checkComments(pageID, data)
        except Exception as e:
            stack = StringIO()
            traceback.print_exc(file=stack)
            self.plugins[Plugin] = str(e)
            self.Logging.output("Cannot execute extension.checkComments() "+str(stack.getvalue()), "warning", True)

        return True

    def loadCommentsFromDB(self):
        query = self.db.query("SELECT * FROM `comments`")

        results = query.fetchall()

        for result in results:
            self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])] = dict()
            self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])]['username'] = str(result['username'])
            self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])]['content'] = str(result['content'])
            self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])]['avatar'] = str(result['avatar'])

        self.Logging.output("+ Loaded "+str(len(results))+" comments from cache.", "", True)

    def checkPage(self, pageID):
        """ Check if page was modified """

        data = self.downloadPage(pageID)

        if self.checkSum(data, pageID) == False:
            return self.checkComments(pageID, data)
        else:
            return False

    def addPagesFromConfig(self):
        section = self.configGetSection('links')

        if section == False:
            self.Logging.output("No pages to scan found, use --add [link] to add new blog entries.", "", False)
            sys.exit(0)

        if len(section) == 0:
            self.Logging.output("No pages to scan found, use --add [link] to add new blog entries.", "", False)
            sys.exit(0)

        for page in section:
            self.addPage(section[page])

    def configCheckChanges(self):
        if os.path.getmtime(self.configDir+"/config") != self.configTime:
            self.Logging.output("Reloading configuration...", "debug", False)
            self.loadConfig()
            self.addPagesFromConfig()
            return True
            
    def getT(self):
        try:
            t = int(self.configGetKey("global", "checktime"))
        except ValueError:
            self.Logging.output("Invalid [global]->checktime value, must be integer not a string", "warning", True)
            t = 30

        self.Logging.output("t = "+str(t), "debug", False)

        return t

    def main(self):
        self.addPagesFromConfig()
        self.loadCommentsFromDB()

        t = self.getT()

        if t == False or t == "False" or t == None:
            t = 5 # 60 seconds

        while True:
            if self.configCheckChanges() == True:
                t = self.getT()

            for pageID in self.pages:
                self.checkPage(pageID)

            time.sleep(t)

    def doPluginsLoad(self):
        """ Plugins support """

        pluginsDir = get_python_lib()+"/libnbnotify/plugins/"

        # fix for python bug which returns invalid path
        if not os.path.isdir(pluginsDir):
            pluginsDir = pluginsDir.replace("/usr/lib/", "/usr/local/lib/")

        # list of disabled plugins
        pluginsDisabled = self.configGetKey('plugins', 'disabled')

        if pluginsDisabled:
            self.disabledPlugins = pluginsDisabled.split(",")


        file_list = glob.glob(pluginsDir+"*.py")


        for Plugin in file_list:
            Plugin = os.path.basename(Plugin)[:-3] # cut directory and .py

            # skip the index
            if Plugin == "__init__":
                continue

            try:
                self.disabledPlugins.index(Plugin)
                self.plugins[Plugin] = 'Disabled'
                self.Logging.output("Disabling "+Plugin, "debug", True)

                continue
            except ValueError:
                self.togglePlugin(False, Plugin, 'activate')

        # add missing plugins
        [self.pluginsList.append(k) for k in self.plugins if k not in self.pluginsList]

    def togglePlugin(self, x, Plugin, Action, liststore=None):
        if Action == 'activate':
            self.Logging.output("Activating "+Plugin, "debug", True)

            # load the plugin
            try:
                exec("import libnbnotify.plugins."+Plugin)
                exec("self.plugins[Plugin] = libnbnotify.plugins."+Plugin)
                exec("self.plugins[Plugin].instance = libnbnotify.plugins."+Plugin+".PluginMain(self)")

                if "_pluginInit" in dir(self.plugins[Plugin].instance):
                    self.plugins[Plugin].instance._pluginInit()

                if not "type" in self.plugins[Plugin].PluginInfo:
                    self.plugins[Plugin].PluginInfo['type'] = 'normal'

                return True

            except Exception as errno:
                stack = StringIO()
                traceback.print_exc(file=stack)
                self.plugins[Plugin] = str(errno)
                self.Logging.output("ERROR: Cannot import "+Plugin+" ("+str(errno)+")\n"+str(stack.getvalue()), "warning", True)
                
                return False

        elif Action == 'deactivate':
            self.Logging.output("Deactivating "+Plugin, "debug", True)
            if self.plugins[Plugin] == 'disabled':
                return True

            try:
                self.plugins[Plugin].instance._pluginDestroy()
                del self.plugins[Plugin].instance
            except Exception:
                pass

            self.plugins[Plugin] = 'Disabled'
            return True













