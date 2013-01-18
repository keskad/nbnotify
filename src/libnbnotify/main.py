#-*- coding: utf-8 -*-
import libnbnotify
import libnbnotify.config
import libnbnotify.browser
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

    # Used Web Browsers (we dont have to load them all...)
    webBrowsers = dict()
    

    # Plugin system adapted from Subget
    disabledPlugins = list()
    plugins=dict()
    pluginsList=list() # ordered list
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain", "User-Agent": "Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.4 (KHTML, like Gecko) Chrome/22.0.1229.79 Safari/537.4", "Accept-charset": "ISO-8859-2,utf-8;q=0.7,*;q=0.3", "Accept-language": "en-US,en;q=0.8,pl;q=0.6"}

    # defaults
    defaultDisabledPlugins = 'libxmpp,nbtwitter'


    def __init__(self):
        self.Logging = libnbnotify.Logging(self)
        self.Config = libnbnotify.config.Config(self, self.configDir+"/"+self.configFile)

        # Deprecated config bindings
        self.configGetKey = self.Config.getKey
        self.configSetKey = self.Config.setKey
        self.configGetSection = self.Config.getSection
        self.configRemoveKey = self.Config.removeKey
        self.saveConfiguration = self.Config.save
        self.configCheckChanges = self.Config.checkChanges


    def loadPasswords(self):
        """ Load passwords storage """

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
        self.Notifications = libnbnotify.Notifications(self)

    def connectionTest(self):
        """ Do a internet connection test """

        try:
            connection = httplib.HTTPConnection(self.Config.getKey("global", "ping_host", "google.com"), 80, timeout=int(self.Config.getKey("connection", "timeout", 5)))
            connection.request("GET", "/")
            return True
        except socket.gaierror:
            return False
            


    def httpGET(self, domain, url, secure=False, cookies='', headers='', redir=0):
        """ Do a HTTP GET request, handle errors """

        if url[0:1] != "/":
            url = "/"+url

        data = False

        # custom headers
        if headers != '':
            h = headers
        else:
            h = self.headers

        # add cookie header
        if cookies != '':
            h['Cookie'] = cookies

        try:
            socket.ssl
        except Exception as e:
            self.Logging.output("SSL is not supported by socket library, switching back to unsecure http connection for link "+str(url), "debug", True)
            secure = False # disable secure connection if SSL is not supported

        try:

            # SSL support
            if secure == True:
                connection = httplib.HTTPSConnection(domain, 443, timeout=int(self.Config.getKey("connection", "timeout", 5)))
            else:
                connection = httplib.HTTPConnection(domain, 80, timeout=int(self.Config.getKey("connection", "timeout", 5)))


            connection.request("GET", str(url), headers=h)
            response = connection.getresponse()
            status = str(response.status)
            data = response.read()
            self.Logging.output(domain+url+", "+status, "debug", False)
            connection.close()

            if status == "302" or status == "301" or status == "303":
                redirection = response.getheader("Location")

                if redir > 5:
                    self.Logging.output("Maximum redirection count exceeded on link "+redirection, "warning", True)
                    return False

                url = urlparse.urlparse(redirection)
                self.Logging.output("Got "+status+", redirecting to: "+redirection, "debug", False)

                # check if we are redirected to SSL connection
                if url.scheme == "https":
                    secure = True
                else:
                    secure = False # unsecure HTTP connection

                # increase redirection count
                redir = redir+1

                self.httpGET(url.netloc, redirection.replace(url.scheme+"://"+url.netloc, ""), secure, cookies, redir)

        except Exception as e:
            self.Logging.output("HTTP request failed, "+str(e), "warning", True)

            # do a connection test on HTTP request failure
            self.cTest = self.connectionTest()

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


    def addService(self, serviceURL):
        """ Add new link from service URL """

        sep = serviceURL.split(".")
        sepL = len(sep)

        # chromium.profile.facebook
        if sepL == 3:
            browser = sep[0]
            profile = sep[1]
            service = sep[2]

        # chromium.facebook
        if sepL == 2:
            browser = sep[0]
            profile = self.Config.getKey("services", "default_profile", "default")
            service = sep[1]

        # facebook
        if sepL == 1:
            browser = self.Config.getKey("services", "default_browser", "chromium")
            profile = self.Config.getKey("services", "default_profile", "default")
            service = sep[0]

        if not browser in self.webBrowsers:
            if os.path.isfile(libnbnotify.browser.__path__[0]+"/"+browser+".py"):
                exec("import libnbnotify.browser."+browser+" as tmpBrowser")

                self.webBrowsers[browser] = tmpBrowser.nbBrowser()
                self.webBrowsers[browser].load(profile)
            else:
                self.Logging.output("Cannot find browser \""+browser+"\", to handle service url "+serviceURL, "warning", True)
                return False


        webBrowser = self.webBrowsers[browser]
        hooks = self.Hooking.getAllHooks("onAddService")
        
        if hooks:
            for Hook in hooks:
                pluginName = str(Hook.im_class).replace("libnbnotify.browser.", "").replace(".nbBrowser", "")

                x = Hook({'service': service, 'browser': webBrowser, 'profile': profile, 'serviceURL': serviceURL})

                if type(x).__name__ == "dict":
                    data = x
                    return self.addPage(data['link'])



    def addPage(self, link):
        """ Add page to database """

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
        errortimeout = int(self.Config.getKey("global", "errortimeout", 300))

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
            self.addPage(section[page])

        #self.configQueueExecute()
            
    def getT(self):
        try:
            t = int(self.Config.getKey("global", "checktime", 120))
        except ValueError:
            self.Logging.output("Invalid [global]->checktime value, must be integer not a string", "warning", True)
            t = 120

        self.Logging.output("t = "+str(t), "debug", False)

        return t

    def initDatabase(self):
        """ Load comments and pages from configuration and database """

        self.addPagesFromConfig()
        self.loadCommentsFromDB()
        return True

    def main(self):
        """ Main loop, connection test, reloading configuration, sending notifications etc. """

        self.cTest = self.connectionTest()
        connectionTestTime = time.time()
        t = self.getT()
        dbInit = False


        # internet connection check, if cannot ping 100% uptime server it will report a warning to console
        if self.cTest == False:
            self.Logging.output("Internet connection problem detected, check your internet connection or DNS settings.", "warning", True)
        else:
            dbInit = self.initDatabase() # load database only if we have internet connection

        if t == False or t == "False" or t == None:
            t = 5 # 60 seconds

        try:
            while True:
                # if configuration was changed check if our interval time of checking new links was changed
                if self.configCheckChanges() == True:
                    t = self.getT()


                #### CONNECTION TEST CODE ####

                # check if routine connection test is enabled (interval > 5)
                if self.Config.getKey("global", "connection_test_time") > 5:
                    # routine check of internet connection every "connection_test_time" of seconds
                    if (time.time()-connectionTestTime) >= int(self.Config.getKey("global", "connection_test_time", 600)): # default is 600 seconds = 10 minutes
                        self.cTest = self.connectionTest()
                        connectionTestTime = time.time() # save last check time

                # so, we will check internet connection every 60 seconds here
                if self.cTest == False:
                    time.sleep(60) # sleep 60 seconds
                    self.cTest = self.connectionTest() # ping google.com and to try again

                    # send a message to console that we are online again
                    if self.cTest == True:
                        self.Logging.output("Finally we are back online", "debug", True)

                        # initialize database if not initialized yet
                        if dbInit == False:
                            dbInit = self.initDatabase()

                    # dont allow to execute all other things like links checking
                    continue


                #### END OF CONNECTION TEST ####

                # restore some pages after failure (eg. internet connection problem)
                self.restoreDisabledPages()

                try:
                    for pageID in self.pages:
                        self.checkPage(pageID)
                        self.Notifications.sendMessages() # send all notifications from one link ;)
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
        pluginsDisabled = self.configGetKey('plugins', 'disabled', self.defaultDisabledPlugins)

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













