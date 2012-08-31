#!/usr/bin/env python
#-*- coding: utf-8 -*-
import os, hashlib, re, BeautifulSoup, sys, subprocess, sqlite3, getopt, time

if sys.version_info[0] >= 3:
    import configparser
    import http.client as httplib
else:
    import ConfigParser as configparser
    import httplib

class MySum:
    def __init__(self):
        self.count = 0

    def step(self, value):
        self.count += value

    def finalize(self):
        return self.count

class Database:
    socket = None
    cursor = None
    dbPath = os.path.expanduser("~/.dpnotify/db_cache.sqlite3")

    def dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def __init__(self):
        newDB = False

        if not os.path.isfile(self.dbPath):
            newDB = True

        self.socket = sqlite3.connect(self.dbPath, check_same_thread = False)
        self.socket.create_aggregate("mysum", 1, MySum)
        self.socket.isolation_level = None
        self.socket.row_factory = self.dict_factory
        self.socket.text_factory = str
        self.cursor = self.socket.cursor()

        if newDB == True:
            self.createEmptyDB()

    def query(self, query):
        return self.cursor.execute(query)

    def createEmptyDB(self):
        print("Creating new database...")
        self.cursor.execute("CREATE TABLE `comments` (comment_id varchar(80) primary key, page_id int(20), content text, username varchar(64), avatar varchar(128));")
        self.socket.commit()




class DobreprogramyNotify:
    Config = dict()
    #Config['connection'] = dict()
    #Config['connection']['timeout'] = 5 # 5 seconds
    iconCacheDir = os.path.expanduser("~/.dpnotify/cache")
    configDir = os.path.expanduser("~/.dpnotify")
    db = None
    pages = dict()

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
        os.system('/usr/bin/notify-send "<b>'+self.pages[pageID]['comments'][id]['username']+'</b> skomentował wpis '+self.pages[pageID]['title'].replace("!", ".")+':" \"'+self.pages[pageID]['comments'][id]['content'].replace("!", ".")+'\" -i '+self.pages[pageID]['comments'][id]['avatar']+' -u low -a dpnotify')



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

    def usage(self):
        print("dpnotify -[short GNU option] [value] --[long GNU option]=[value]")
        print("\nUsage:\n")
        print("--help, -h (this message)")
        print("--add, -a (add link to database)")
        print("--remove, -r (remove link from database)")
        print("--list, -l (list all links)")
        print("--daemonize, (fork to background and run as userspace daemon)")

    def daemonize (self, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        '''This forks the current process into a daemon.
        The stdin, stdout, and stderr arguments are file names that
        will be opened and be used to replace the standard file descriptors
        in sys.stdin, sys.stdout, and sys.stderr.
        These arguments are optional and default to /dev/null.
        Note that stderr is opened unbuffered, so
        if it shares a file with stdout then interleaved output
        may not appear in the order that you expect.
        '''

        # Do first fork.
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)   # Exit first parent.
        except OSError as e:
            sys.stderr.write ("fork #1 failed: (%d) %s\n" % (e.errno, e.strerror) )
            sys.exit(1)

        # Decouple from parent environment.
        os.chdir("/")
        os.umask(0)
        os.setsid()

        # Do second fork.
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)   # Exit second parent.
        except OSError as e:
            sys.stderr.write ("fork #2 failed: (%d) %s\n" % (e.errno, e.strerror) )
            sys.exit(1)

        # Redirect standard file descriptors.
        si = open(stdin, 'r')
        so = open(stdout, 'a+')
        se = open(stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

    def getopt(self):
        if not os.path.isdir(self.iconCacheDir):
            os.system("mkdir -p "+self.iconCacheDir)

        self.db = Database()
        self.loadConfig()

        try:
            opts, args = getopt.getopt(sys.argv[1:], "ha:r:l", ["help", "add=", "remove=", 'list', 'daemon'])
        except getopt.GetoptError as err:
            print("Error: "+str(err)+", Try --help for usage\n\n")
            self.usage()
            sys.exit(2)

        for o, a in opts:
            if o in ('-h', '--help'):
                 self.usage()
                 sys.exit(2)

            if o in ('-a', '--add'):
                self.configSetKey('links', hashlib.md5(a).hexdigest(), a)
                self.saveConfiguration()
                sys.exit(0)

            if o in ('-l', '--list'):
                links = self.configGetSection('links')

                if links == False:
                    print("No links in database.")
                    sys.exit(0)

                for link in links:
                    print(links[link])

                sys.exit(0)

            if o in ('-r', '--remove'):
                links = self.configGetSection('links')

                if links == False:
                    print("No links in database.")
                    sys.exit(0)

                pos = None

                for link in links:
                    if links[link] == a:
                        pos = link
                        break

                if pos is not None:
                    links.pop(pos)
                    print("Removed.")
                    self.saveConfiguration()
                else:
                    print("Link not found, nothing changed.")

                sys.exit(0)

            if o in '--daemon':
                self.daemonize()

        self.main()
if __name__ == "__main__":
    app = DobreprogramyNotify()
    app.getopt()
