#-*- coding: utf-8 -*-
import libnbnotify
import socket
import ssl
import json
import asyncore
import re
import sys
from threading import Thread
import string
import random
import os
import BaseHTTPServer, SimpleHTTPServer

PluginInfo = {'Requirements' : { 'OS' : 'All'}, 'API': 2, 'Authors': 'webnull', 'domain': '', 'type': 'extension', 'isPlugin': False, 'Description': 'Remote control throught sockets'}
app = ""

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))

class SocketInterface(SimpleHTTPServer.SimpleHTTPRequestHandler):
    """ Very simple socket interface """

    def log_message(self, format, *args):
        return False

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


    def do_POST(self):
        contentLen = int(self.headers.getheader('content-length'))
        postBody = self.rfile.read(contentLen)

        # response
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(self.handle_read(postBody))

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write("Hello world.")

    def handle_read(self, data):
        global app

        self.app = app

        if data:
            if data == "ping":
                return "pong"

            try:
                #if t == False:
                #    return "Error: Cannot parse HTTP request, "+str(t)+", "+str(jsonData)

                if data == False:
                    return "Error: Cannot parse HTTP request, empty request, "+str(jsonData)

                text = json.loads(data)

                if text['function'] == "handle_read" or text['function'] == "__init__" or text['function'] == "httpRequestParser":
                    return "Error: Function not avaliable"

                if hasattr(self, text['function']):
                    exec("r = str(self."+text['function']+"(text['data']))")
                else:
                    r = "Error: Function not found"

                self.app.Logging.output("Socket::GET="+str(text['function'])+"&addr="+str(self.client_address[0]), "debug", False)

                # send response                
                return json.dumps({'response': r})

            except Exception as e:
                self.app.Logging.output("SubgetSocketInterface: Cannot parse json data, is the client bugged? "+str(e), "warning", True)
                return "Error: "+str(e)

class SocketServer:
    """ Very simple connections listener """

    host = "127.0.0.1"
    port = 9954

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def serve(self):
        httpd = BaseHTTPServer.HTTPServer((self.host, self.port), SocketInterface)
        httpd.serve_forever()


class PluginMain(libnbnotify.Plugin):
    name = "bus"
    host = "127.0.0.1"
    port = 9954
    bus = ""

    def _pluginInit(self):
        #self.initSSL()
        global app
        app = self.app
        
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
            
    #def initSSL(self):
    #   path = os.path.expanduser("~/.nbnotify/ssl")
       
       # create ssl directory
    #   if not os.path.isdir(path):
    #      os.mkdir(path)
        
    #   if not os.path.isfile(path+"/private.pem"):
    #       passwd = id_generator(size=32)
           
    #       self.app.Logging.output("Cannot find SSL cert, creating new one...", "debug", True)
    #       os.system("openssl genrsa -out "+path+"/private.pem 1024")
    #       os.system("openssl rsa -in "+path+"/private.pem -pubout > "+path+"/public.pem")


    def startServer(self):
        try:
            self.app.Logging.output("Socket server is running on "+str(self.host)+":"+str(self.port), "debug", False)
            self.bus = SocketServer(self.host, self.port)
            self.thread = Thread(target=self.bus.serve)
            self.thread.setDaemon(True)
            self.thread.start()
        except Exception as e:
            self.app.Logging.output("Only one instance of nbnotify is allowed, "+str(e), "debug", False)
            sys.exit(0)



