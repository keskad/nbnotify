#-*- coding: utf-8 -*-
import libnbnotify
import libnbnotify.config
import traceback
import os, hashlib, re, BeautifulSoup, sys, time, glob, traceback
import sqlite3
from distutils.sysconfig import get_python_lib
import socket
import copy
import urlparse

if sys.version_info[0] >= 3:
    import configparser
    import http.client as httplib
    import io as StringIO
else:
    from StringIO import StringIO
    import ConfigParser as configparser
    import httplib


class nbnotify:
    cli = False
    Config = dict()
    #Passwords = dict()

    # queue
    configQueue = dict()
    configQueue['links'] = dict()

    iconCacheDir = os.path.expanduser("~/.nbnotify/cache")
    configDir = os.path.expanduser("~/.nbnotify")
    configFile = "config"
    db = None
    pages = dict()
    disabledPages = dict() # Page => Reason
    Hooking = libnbnotify.Hooking()

    # Plugin system adapted from Subget
    disabledPlugins = list()
    plugins=dict()
    pluginsList=list() # ordered list
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain", "User-Agent": "Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.4 (KHTML, like Gecko) Chrome/22.0.1229.79 Safari/537.4", "Accept-charset": "ISO-8859-2,utf-8;q=0.7,*;q=0.3", "Accept-language": "en-US,en;q=0.8,pl;q=0.6"}


    def __init__(self):
        self.Logging = libnbnotify.Logging(self)
        self.Config = libnbnotify.config.Config(self, self.configDir+"/"+self.configFile)

        # Config bindings
        self.configGetKey = self.Config.getKey
        self.configSetKey = self.Config.setKey
        self.configGetSection = self.Config.getSection
        self.configRemoveKey = self.Config.removeKey
        self.saveConfiguration = self.Config.save
        self.configCheckChanges = self.Config.checkChanges


    def shellquote(self, s):
        return "'" + s.replace("'", "'\\''") + "'"

    def loadPasswords(self):
        self.Passwords = libnbnotify.config.Config(self, self.configDir+"/auth")

        if not os.path.isfile(self.configDir+"/auth"):
            w = open(self.configDir+"/auth", "w")
            w.write("")
            w.close()

        self.Passwords.loadConfig()


    def loadConfig(self):
        """ Parsing configuration ini file """

        configPath = self.configDir + "/" +self.configFile

        if not os.path.isdir(self.configDir):
            try:
                os.mkdir(self.configDir)
            except Exception:
                print("Cannot create "+configPath+" directory, please check your permissions")

        if not os.path.isfile(configPath):
            os.system("cp /usr/share/nbnotify/config-example "+configPath)

        if not os.path.isfile(configPath):
            os.system("cp /usr/local/share/nbnotify/config-example "+configPath)

        self.Config.loadConfig()


    def httpGET(self, domain, url, secure=False, cookies=''):
        """ Do a HTTP GET request, handle errors """

        if url[0:1] != "/":
            url = "/"+url

        data = False

        h = self.headers

        # add cookie header
        if cookies != '':
            h['Cookie'] = cookies

        try:
            connection = httplib.HTTPConnection(domain, 80, timeout=int(self.configGetKey("connection", "timeout")))
            connection.request("GET", str(url), headers=h)
            response = connection.getresponse()
            status = str(response.status)
            data = response.read()
            self.Logging.output("GET: "+domain+url+", "+status, "debug", False)
            connection.close()

            if status == "302":
                #self.redirections = self.redirections + 1

                #if self.redirections > 5:
                #    return False

                redirection = response.getheader("Location")
                url = urlparse.urlparse(redirection)
                self.Logging.output("Got 302, redirecting to: "+redirection, "debug", False)
                return self.httpGET(url.netloc, redirection.replace(url.scheme+"://"+url.netloc, ""))
                

            if len(data) == 0 and status == "301":
                self.Logging.output("Adding \"www\" subdomain to url", "warning", True)

                try:
                    socket.ssl
                except Exception as e:
                    self.Logging.output("SSL is not supported by socket library, switching back to unsecure http connection for link "+str(url), "debug", True)
                    secure = False # disable secure connection if SSL is not supported

                # support SSL
                if secure == True:
                    connection = httplib.HTTPSConnection("www."+domain, 443, timeout=int(self.configGetKey("connection", "timeout")))
                else:
                    connection = httplib.HTTPConnection("www."+domain, 80, timeout=int(self.configGetKey("connection", "timeout")))

                connection.request("GET", str(url), headers=h)
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

        s = False # SSL

        if self.pages[pageID]['secure'] == True:
            s = True

        return self.httpGET(self.pages[pageID]['domain'], str(self.pages[pageID]['link']), secure=s, cookies=str(self.pages[pageID]['cookies']))


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



    def addPage(self, link, editingConfig=False):
        m = hashlib.md5(link).hexdigest()
        originalLink = link
        oldM = m

        strippedLink = self.stripLink(link)

        for k in self.pages:
            if self.pages[k]['link_id'] == link:
                self.Logging.output("Skipping adding "+strippedLink+" - duplicate.", "debug", False)
                return False

        hooks = self.Hooking.getAllHooks("onAddPage")
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

            if not "secure" in data:
                data['secure'] = False

            if not "cookies" in data:
                data['cookies'] = ""

            if not "reallink" in data:
                data['reallink'] = strippedLink
            else:
                m = hashlib.md5(data['reallink']).hexdigest()
                link = data['reallink']

            try:
                self.pages[str(m)] = {'hash': '', 'link': data['link'], 'link_id': strippedLink, 'comments': dict(), 'extension': data['extension'], 'domain': data['domain'], 'data': data['data'], 'dontDownload': data['dontDownload'], 'id': data['id'], 'secure': data['secure'], 'exceptions': 0, 'cookies': data['cookies'], 'reallink': data['reallink']}

                if len(strippedLink) > 40:
                    strippedLink = strippedLink[0:40]+"(...)"

                self.Logging.output("Adding "+link, "debug", False)

                # doesnt exists or changed id
                if str(self.configGetKey("links", oldM)) == "False" or m != oldM:
                    self.configSetKey("links", oldM, link)
                    self.Config.renameAllKeys(oldM, m)

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
        try:
            errortimeout = int(self.Config.getKey("global", "errortimeout"))
        except ValueError:
            self.Config.setKey("global", "errortimeout", "300") # 5 minutes by default
            errortimeout = 300

        if errortimeout == 0:
            self.Config.setKey("global", "errortimeout", "300")
            errortimeout = 300

        if not pageID in self.disabledPages:
            self.pages[pageID]['exceptions'] = int(time.time()+errortimeout)
            self.disabledPages[pageID] = reason
            self.Logging.output("Disabling page "+pageID+" due to found errors. "+reason, "warning", True)
            return True

    def restoreDisabledPages(self):
        timeNow = int(time.time())

        a = copy.copy(self.disabledPages)

        for pageID in a:
            if self.pages[pageID]['exceptions'] < timeNow:
                self.Logging.output("Enabling page "+pageID+" again", "warning", True)
                del self.disabledPages[pageID]


    def checkComments(self, pageID, data=''):
        """ Parse all comments """

        try:
            extension = self.pages[pageID]['extension']
            extension.checkComments(pageID, data)
            self.pages[pageID]['exceptions'] = 0
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

        try:
            section = dict(self.configGetSection('links'))
        except TypeError:
            section = False

        if section == False:
            self.Logging.output("No pages to scan found, use --add [link] to add new blog entries.", "", False)
            sys.exit(0)

        if len(section) == 0:
            self.Logging.output("No pages to scan found, use --add [link] to add new blog entries.", "", False)
            sys.exit(0)

        for page in section:
            self.addPage(section[page], editingConfig=False)

        #self.configQueueExecute()
            
    def getT(self):
        try:
            t = int(self.configGetKey("global", "checktime"))
        except ValueError:
            self.Logging.output("Invalid [global]->checktime value, must be integer not a string", "warning", True)
            t = 120

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

                self.restoreDisabledPages()

                try:
                    for pageID in self.pages:
                        self.checkPage(pageID)
                except RuntimeError:
                    pass

                time.sleep(t)
        except KeyboardInterrupt:
            self.Config.save()
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













