#-*- coding: utf-8 -*-
import libnbnotify
import traceback
import os, hashlib, re, BeautifulSoup, sys, time, glob, traceback
import sqlite3
from distutils.sysconfig import get_python_lib

if sys.version_info[0] >= 3:
    import configparser
    import http.client as httplib
    import io as StringIO
else:
    from StringIO import StringIO
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
    disabledPages = dict() # Page => Reason
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
        """ Set configuration key """

        if not Section in self.Config:
            self.Config[Section] = dict()

        self.Config[Section][Option] = str(Value)

        return True

    def configRemoveKey(self, Section, Option):
        return self.Config[Section].pop(Option)

    def saveConfiguration(self):
        """ Save configuration to file """

        Output = ""
        r = False

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
            r = True
        except Exception as e:
            print("Cannot save configuration to file "+self.configDir+"/config")
            r = False

        self.configTime = os.path.getmtime(self.configDir+"/config")
        return r

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

    def httpGET(self, domain, url):
        """ Do a HTTP GET request, handle errors """

        if url[0:1] != "/":
            url = "/"+url

        data = False

        try:
            connection = httplib.HTTPConnection(domain, 80, timeout=int(self.configGetKey("connection", "timeout")))
            connection.request("GET", str(url))
            response = connection.getresponse()
            status = str(response.status)
            data = response.read()
            self.Logging.output("GET: "+domain+url+", "+status, "debug", False)
            connection.close()

            if len(data) == 0 and status == "301" :
                self.Logging.output("Adding \"www\" subdomain to url", "warning", True)
                connection = httplib.HTTPConnection("www."+domain, 80, timeout=int(self.configGetKey("connection", "timeout")))
                connection.request("GET", str(url))
                response = connection.getresponse()
                status = str(response.status)
                data = response.read()
                self.Logging.output("GET: www."+domain+url+", "+status, "debug", False)
                connection.close()
        except Exception as e:
            self.Logging.output("HTTP request failed, "+str(e), "warning", True)

        return data

    def downloadPage(self, pageID):
        """ Download page and check md5 sum """

        return self.httpGET(self.pages[pageID]['domain'], str(self.pages[pageID]['link']))

    def checkSum(self, data, pageID):
        # check md5 sums

        if data == False:
            return False

        m = hashlib.md5(data).digest()

        if m == self.pages[pageID]['hash']:
            return True

        self.pages[pageID]['hash'] = m
        return False

    def setType(self, link, Type):
        m = hashlib.md5(link).hexdigest()
        self.configSetKey('linktypes', m, Type)
        return m

    def removePage(self, pageID):
        """ Remove page from list of pages """

        m = hashlib.md5(pageID).hexdigest()

        if m in self.pages:
            self.pages.pop(m)
            self.configRemoveKey("links", m)
            return True

        return False

    def stripLink(self, link):
        """ Removes http/https and www """

        return link.replace("http://", "").replace("https://", "").replace("www.", "")

    def addPage(self, link):
        strippedLink = self.stripLink(link)

        for k in self.pages:
            if self.pages[k]['link_id'] == link:
                self.Logging.output("Skipping adding "+strippedLink+" - duplicate.", "debug", False)
                return False

        hooks = self.Hooking.getAllHooks("onAddPage")
        m = hashlib.md5(link).hexdigest()
        data = False
        staticPlugin = str(self.configGetKey("linktypes", m))
        breakHere = False

        # search for plugin that handles link correctly
        if hooks:
            for Hook in hooks:
                pluginName = str(Hook.im_class).replace("libnbnotify.plugins.", "").replace(".PluginMain", "")

                # found specified plugin
                if staticPlugin == pluginName:
                    breakHere = True 

                try:
                    x = Hook({'link': link, 'staticPlugin': staticPlugin})

                    if type(x).__name__ == "dict":
                        data = x
                        break

                except Exception as e:
                    self.Logging.output("Cannot execute hook "+str(Hook)+", error: "+str(e), "warning", True)

                if breakHere == True:
                    break

        if type(data).__name__ == "dict":

            # default values
            if not "data" in data:
                data['data'] = False

            if not "dontDownload" in data:
                data['dontDownload'] = False

            if not "id" in data:
                data['id'] = False

            try:
                self.pages[str(m)] = {'hash': '', 'link': data['link'], 'link_id': strippedLink, 'comments': dict(), 'extension': data['extension'], 'domain': data['domain'], 'data': data['data'], 'dontDownload': data['dontDownload'], 'id': data['id']}
                self.Logging.output("Adding "+strippedLink, "", False)

                if str(self.configGetKey("links", m)) == "False":
                    self.configSetKey("links", m, link)

                return True
            except Exception as e:
                buffer = StringIO()
                traceback.print_exc(file=buffer)
                self.Logging.output("Cannot add "+strippedLink+", exception: "+str(buffer.getvalue()), "warning", True, skipDate=True)

        else:
            self.Logging.output("No any suitable extension supporting link format \""+strippedLink+"\" found", "warning", True)
            return False

    def addCommentToDB(self, pageID, id, localAvatar):
        try:
            self.db.cursor.execute("INSERT INTO `comments` (page_id, comment_id, content, username, avatar) VALUES (?, ?, ?, ?, ?)", (str(pageID), str(id), str(self.pages[str(pageID)]['comments'][id]['content']), str(self.pages[str(pageID)]['comments'][id]['username']), str(localAvatar)))
        except sqlite3.IntegrityError:
            pass # sqlite3.IntegrityError: column comment_id is not unique


    def notifyNew(self, pageID, id, template="%username% skomentował \"%title%\""):
        """ Create new notification from data """

        self.Hooking.executeHooks(self.Hooking.getAllHooks("onNotifyNew"), [pageID, id, template])
        #os.system('/usr/bin/notify-send "<b>'+self.shellquote(self.pages[pageID]['comments'][id]['username'])+'</b> skomentował wpis '+self.shellquote(self.pages[pageID]['title'].replace("!", "."))+':" \"'+self.shellquote(self.pages[pageID]['comments'][id]['content']).replace("!", ".")+'\" -i '+self.self.pages[pageID]['comments'][id]['avatar']+' -u low -a dpnotify')

        return True

    def notifyNewData(self, data, title='', icon='', pageID=''):
        self.Hooking.executeHooks(self.Hooking.getAllHooks("onNotifyNewData"), [data, title, pageID, icon])

        return True

    def disablePage(self, pageID, reason=''):
        self.disabledPages[pageID] = reason
        self.Logging.output("Disabling page "+pageID+" due to found errors.")
        return True

    def checkComments(self, pageID, data=''):
        """ Parse all comments """

        try:
            extension = self.pages[pageID]['extension']
            extension.checkComments(pageID, data)
        except Exception as e:
            stack = StringIO()
            traceback.print_exc(file=stack)
            self.Logging.output("Cannot execute extension.checkComments() "+str(stack.getvalue()), "warning", True)
            self.disablePage(pageID, str(stack.getvalue()))

        return True

    def loadCommentsFromDB(self):
        query = self.db.query("SELECT * FROM `comments`")

        results = query.fetchall()

        for result in results:
            try:
                self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])] = dict()
                self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])]['username'] = str(result['username'])
                self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])]['content'] = str(result['content'])
                self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])]['avatar'] = str(result['avatar'])
            except KeyError:
                # delete comments that dont belongs to any page
                self.db.query("DELETE FROM `comments` WHERE `comment_id`='"+str(result['comment_id'])+"'")

        self.Logging.output("+ Loaded "+str(len(results))+" comments from cache.", "", True)

    def checkPage(self, pageID):
        """ Check if page was modified """

        if not pageID in self.pages:
            return False

        if pageID in self.disabledPages:
            self.Logging.output(self.pages[pageID]['link']+" was disabled because of errors.")
            return False


        try:
            # twitter etc. throught API support
            if self.pages[pageID]['dontDownload'] == True:
                data = self.pages[pageID]['data']
            else:
                data = self.downloadPage(pageID)

            if self.checkSum(data, pageID) == False:
                return self.checkComments(pageID, data)
            else:
                return False
        except KeyError:
            self.Logging.output("Page removed while parsing by extension, propably removed from external application using API")
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

        try:
            while True:
                if self.configCheckChanges() == True:
                    t = self.getT()

                try:
                    for pageID in self.pages:
                        self.checkPage(pageID)
                except RuntimeError:
                    pass

                time.sleep(t)
        except KeyboardInterrupt:
            print("Got keyboard interrupt, exiting.")
            sys.exit(0)

    def doPluginsLoad(self):
        """ Plugins support """

        pluginsDir = get_python_lib()+"/libnbnotify/plugins/"

        if os.path.isdir(pluginsDir.replace("dist-packages/", "")):
            pluginsDir = pluginsDir.replace("dist-packages/", "")

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
                self.togglePlugin(Plugin, 'activate')

        # add missing plugins
        [self.pluginsList.append(k) for k in self.plugins if k not in self.pluginsList]

    def togglePlugin(self, Plugin, Action):
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













