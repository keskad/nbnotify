#-*- coding: utf-8 -*-
import libnbnotify
import os, hashlib, re, BeautifulSoup, sys, time, glob, traceback
from distutils.sysconfig import get_python_lib

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
            print("Saving to "+self.configDir+"/config")
            Handler = open(self.configDir+"/config", "wb")
            Handler.write(Output)
            Handler.close()
        except Exception as e:
            print("Cannot save configuration to file "+self.configDir+"/config")

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
                print("Error parsing configuration file from "+self.configDir+"/config, error: "+str(e), "critical", True)
                sys.exit(os.EX_CONFIG)

            # all configuration sections
            Sections = Parser.sections()

            for Section in Sections:
                Options = Parser.options(Section)
                self.Config[Section] = dict()

                # and configuration variables inside of sections
                for Option in Options:
                    self.Config[Section][Option] = Parser.get(Section, Option)

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

        connection = httplib.HTTPConnection("www.dobreprogramy.pl", 80, timeout=int(self.configGetKey("connection", "timeout")))
        connection.request("GET", "/"+str(self.pages[pageID]['link']))
        response = connection.getresponse()
        data = response.read()
        print("GET: www.dobreprogramy.pl/"+self.pages[pageID]['link'])
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
        link = link.replace("http://www.dobreprogramy.pl/", "").replace("http://dobreprogramy.pl", "").replace("dobreprogramy.pl", "").replace("www.dobreprogramy.pl", "")
        match = re.findall(",([0-9]+).html", link)

        if len(match) == 0:
            print("Invalid link format.")
            return False

        if str(match[0]) in self.pages:
            return False

        print("+ Adding dobreprogramy.pl/"+link)

        self.pages[str(match[0])] = {'hash': '', 'link': link, 'comments': dict()}



    def notifyNew(self, pageID, id):
        self.Hooking.executeHooks(self.Hooking.getAllHooks("onNotifyNew"), [pageID, id])
        #os.system('/usr/bin/notify-send "<b>'+self.shellquote(self.pages[pageID]['comments'][id]['username'])+'</b> skomentował wpis '+self.shellquote(self.pages[pageID]['title'].replace("!", "."))+':" \"'+self.shellquote(self.pages[pageID]['comments'][id]['content']).replace("!", ".")+'\" -i '+self.self.pages[pageID]['comments'][id]['avatar']+' -u low -a dpnotify')



    def downloadAvatar(self, avatar):
        """ Download avatar to local cache """

        m = hashlib.md5(avatar).hexdigest()
        icon = self.iconCacheDir+"/"+m+".png"

        if not os.path.isfile(icon):
            url = avatar.replace("http://avatars.dpcdn.pl", "").replace("http://www.avatars.dpcdn.pl", "").replace("www.avatars.dpcdn.pl", "").replace("avatars.dpcdn.pl", "")

            connection = httplib.HTTPConnection("avatars.dpcdn.pl", 80, timeout=int(self.configGetKey("connection", "timeout")))
            connection.request("GET", url)
            response = connection.getresponse()
            data = response.read()
            connection.close()

            w = open(icon, "wb")
            w.write(data)
            w.close()
            print("GET: avatars.dpcdn.pl/"+url)
            
        return icon

    def checkComments(self, pageID, data=''):
        """ Parse all comments """

        soup = BeautifulSoup.BeautifulSoup(data)

        self.pages[pageID]['title'] = str(soup.html.head.title.string)
        commentsHTML = soup.findAll('div', {'class': "odd item"})
        commentsEven = soup.findAll('div', {'class': "even item"})
        commentsHTML = commentsHTML+commentsEven

        isNew = False
        commentsList = dict()

        for comment in commentsHTML:
            # comment id - first <img src="(.*)"
            cSoup = BeautifulSoup.BeautifulSoup(str(comment))
            id = str(cSoup.div['id'])

            if not id in self.pages[str(pageID)]['comments']:
                isNew = True

            avatar = str(cSoup.img['src'])
            localAvatar = self.downloadAvatar(avatar)
            self.pages[str(pageID)]['comments'][id] = {'avatar': localAvatar}

            # user name - <a class="color-inverse"
            cInv = cSoup.findAll("a", {'class': 'color-inverse'})

            # guests users
            if len(cInv) == 0: 
                cInv = cSoup.findAll("span")
                nSoup = BeautifulSoup.BeautifulSoup(str(cInv[0]))
                self.pages[str(pageID)]['comments'][id]['username'] = str(nSoup.span.string)

            else:
                nSoup = BeautifulSoup.BeautifulSoup(str(cInv[0]))
                self.pages[str(pageID)]['comments'][id]['username'] = str(nSoup.a.string)

            # comment content - <div class="text-h75 tresc"
            nSoup = str(cSoup.findAll("div", {'class': "text-h75 tresc"})[0]).replace('<div class="text-h75 tresc">', '').replace('</div>', '')
            self.pages[str(pageID)]['comments'][id]['content'] = nSoup
           # self.pages[str(pageID)]['comments'][id]['content'] = 

            if isNew == True:
                self.notifyNew(pageID, id)
                try:
                    self.db.cursor.execute("INSERT INTO `comments` (page_id, comment_id, content, username, avatar) VALUES (?, ?, ?, ?, ?)", (str(pageID), str(id), str(self.pages[str(pageID)]['comments'][id]['content']), str(self.pages[str(pageID)]['comments'][id]['username']), str(localAvatar)))
                except sqlite3.IntegrityError:
                    pass # sqlite3.IntegrityError: column comment_id is not unique
                isNew = False


        

        return True

    def loadCommentsFromDB(self):
        query = self.db.query("SELECT * FROM `comments`")

        results = query.fetchall()

        for result in results:
            self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])] = dict()
            self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])]['username'] = str(result['username'])
            self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])]['content'] = str(result['content'])
            self.pages[str(result['page_id'])]['comments'][str(result['comment_id'])]['avatar'] = str(result['avatar'])

        print("+ Loaded "+str(len(results))+" comments from cache.")

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
            print("No pages to scan found, use --add [link] to add new blog entries.")
            sys.exit(0)

        if len(section) == 0:
            print("No pages to scan found, use --add [link] to add new blog entries.")
            sys.exit(0)

        for page in section:
            self.addPage(section[page])
            

    def main(self):
        self.addPagesFromConfig()
        self.loadCommentsFromDB()

        try:
            t = int(self.configGetKey("global", "checktime"))
        except ValueError:
            print("Invalid [global]->checktime value, must be integer not a string")
            t = 30

        if t == False or t == "False" or t == None:
            t = 5 # 60 seconds

        while True:
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
                print("Disabling "+Plugin)

                continue
            except ValueError:
                self.togglePlugin(False, Plugin, 'activate')

        # add missing plugins
        [self.pluginsList.append(k) for k in self.plugins if k not in self.pluginsList]

    def togglePlugin(self, x, Plugin, Action, liststore=None):
        if Action == 'activate':
            print("Activating "+Plugin)

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
                stack = StringIO.StringIO()
                traceback.print_exc(file=stack)
                self.plugins[Plugin] = str(errno)
                print("ERROR: Cannot import "+Plugin+" ("+str(errno)+")\n"+str(stack.getvalue()))
                
                return False

        elif Action == 'deactivate':
            print("Deactivating "+Plugin)
            if self.plugins[Plugin] == 'disabled':
                return True

            try:
                self.plugins[Plugin].instance._pluginDestroy()
                del self.plugins[Plugin].instance
            except Exception:
                pass

            self.plugins[Plugin] = 'Disabled'
            return True
































