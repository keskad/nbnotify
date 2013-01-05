#-*- coding: utf-8 -*-
import libnbnotify
import socket
import json
import asyncore
import re
import sys
from threading import Thread

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Remote control throught sockets'}

class SocketInterface(asyncore.dispatcher_with_send):
    """ Very simple socket interface """

    app = None

    def ping(self, data=''):
        return "pong";

    def getConfigAndEntries(self, data=''):
        """ Returns all configuration variables and links """

        return [self.app.configGetSection('links'), self.app.Config.Config]

    def getAllEntries(self, data=''):
        """ Returns all links from database """

        return self.app.configGetSection('links')

    def notifyNewData(self, data):
        """ Create new notification from data """

        content = data['data']
        title = data['title']
        icon = data['icon']
        pageID = data['pageid']

        self.app.notifyNewData(content, title, icon, pageID)

    def configSetKey(self, data):
        """ Set configuration key """

        Section = data['section']
        Option = data['option']
        Value = data['value']

        return self.app.configSetKey(Section, Option, Value)
        

    def saveConfiguration(self, data=''):
        """ Force save configuration to file """

        return self.app.saveConfiguration()

    def configGetSection(self, data):
        """ Returns section as dictionary 

            Args:
              Section - name of section of ini file ([section] header)

            Returns:
              Dictionary - on success
              False - on false

        """

        return self.app.configGetSection(data)

    def configGetKey(self, data):
        """ Returns value of Section->Value configuration variable

            Args:
              Section - name of section of ini file ([section] header)
              Key - variable name

            Returns:
              False - when section or key does not exists
              False - when value of variable is "false" or "False" or just False
              string value - value of variable
        """

        Section = data['section']
        Key = data['key']

        return self.app.configGetKey(Section, Key)

    def addPage(self, link):
        """ Add page to database, return True if added sucessfuly """

        return self.app.addPage(link)

    def setType(self, data):
        """ Set specified extension to handle specified link
            Return md5 hash of link on success
        """

        Link = data['link']
        Type = data['type']

        return self.app.setType(Link, Type) 

    def removePage(self, pageID):
        """ Remove page with specified pageID """

        return self.app.removePage(pageID)

    def loadCommentsFromDB(self, data=''):
        """ Reload comments cache from SQLite database """

        return self.app.loadCommentsFromDB()

    def configCheckChanges(self, data=''):
        """ Reload configuration if changed """

        return self.app.configCheckChanges()

    def togglePlugin(self, data):
        """ Activate or deactivate plugin
            Plugin - name of plugin
            Toggle - True or False
        """

        Plugin = data['name']
        Toggle = data['toggle']

        if Toggle == True:
            return self.app.togglePlugin(Plugin, 'activate')

        return self.app.togglePlugin(Plugin, 'deactivate')


    def __init__(self, socket, app, addr):
        asyncore.dispatcher_with_send.__init__(self)
        self.set_socket(socket)
        self.app = app
        self.addr = addr

    def httpResponse(self, data):
        return """HTTP/1.1 200 OK
Content-Type: text/xml;charset=utf-8
Content-Length: """+str(len(data))+"""

"""+data

    def httpRequestParser(self, data):
        if data[0:4] == "POST":
            t = re.findall(r"POST ([0-9A-Za-z\?\#\@$\%\!\.\,\:\;\'\|\-\+\/]+) ", data)

            if len(t) == 0:
                return "Invalid POST request", False

            page = t[0]
        else:
            return "Not a POST request", False


        # headers
        t = re.findall(r"(?P<name>.*?): (?P<value>.*?)\r\n", data)

        headers = dict()

        for header in t:
            headers[header[0]] = header[1]

        t = str(data).split('\r\n')
        content = False

        for line in t:
            if line[0:1] == "{":
                content = line
                break
        
        return page, content

        self.app.Logging.output("Socket::HTTP:GET "+str(page), "debug", False)

    def handle_read(self):
        data = self.recv(8192)

        if data:
            if data == "ping":
                self.send("pong")
                return False

            try:
                t, jsonData = self.httpRequestParser(data)

                if t == False:
                    self.send(self.httpResponse("Error: Cannot parse HTTP request, "+str(t)+", "+str(jsonData)))
                    return False

                if jsonData == False:
                    self.send(self.httpResponse("Error: Cannot parse HTTP request, empty request, "+str(t)+", "+str(jsonData)))
                    return False

                text = json.loads(jsonData)

                if text['function'] == "handle_read" or text['function'] == "__init__" or text['function'] == "httpRequestParser":
                    self.send(self.httpResponse("Error: Function not avaliable"))
                    return False

                if hasattr(self, text['function']):
                    exec("r = str(self."+text['function']+"(text['data']))")
                else:
                    r = "Error: Function not found"

                self.app.Logging.output("Socket::GET="+str(text['function'])+"&addr="+str(self.addr), "debug", False)

                # send response                
                self.send(self.httpResponse(json.dumps({'response': r})))

            except Exception as e:
                self.app.Logging.output("SubgetSocketInterface: Cannot parse json data, is the client bugged? "+str(e), "warning", True)
                self.send(self.httpResponse("Error: "+str(e)))

class SocketServer(asyncore.dispatcher):
    """ Very simple connections listener """

    app = None

    def __init__(self, host, port, app):
        self.app = app
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM) # IPv6 support will be implemented later
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(3)

    def handle_accept(self):
        pair = self.accept()

        if pair is None:
            pass
        else:
            sock, addr = pair
            handler = SocketInterface(sock, self.app, addr)

class PluginMain(libnbnotify.Plugin):
    name = "bus"
    host = "127.0.0.1"
    port = 9954

    def _pluginInit(self):
        self.host = str(self.app.Config.getKey("bus_socket", "host", "127.0.0.1"))

        if self.app.Config.getKey("bus_socket", "port") == False:
            self.app.Config.setKey("bus_socket", "port", 9954)
        else:
            try:
                self.port = int(self.app.Config.getKey("bus_socket", "port"))
            except ValueError:
                self.port = 9954
                self.app.Config.setKey("bus_socket", "port", 9954)


        if self.app.cli == False:
            self.startServer()
            return True
        else:
            return False

    def startServer(self):
        try:
            self.app.Logging.output("Socket server is running on "+str(self.host)+":"+str(self.port), "debug", False)
            self.bus = SocketServer(self.host, self.port, self.app)
            self.thread = Thread(target=asyncore.loop)
            self.thread.setDaemon(True)
            self.thread.start()
        except Exception as e:
            self.app.Logging.output("Only one instance of nbnotify is allowed, "+str(e), "debug", False)
            sys.exit(0)



