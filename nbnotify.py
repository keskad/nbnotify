#!/usr/bin/env python
#-*- coding: utf-8 -*-
import libnbnotify.main, libnbnotify.database, libnbnotify.plugins, os, sys, getopt, hashlib

def parseArgs(app):
    """ Args parser """

    if not os.path.isdir(app.iconCacheDir):
        os.system("mkdir -p "+app.iconCacheDir)

    app.db = libnbnotify.database.Database()
    app.loadConfig()

    try:
        opts, args = getopt.getopt(sys.argv[1:], "ha:r:lt:p", ["help", "append=", "remove=", 'list', 'daemonize', 'type', 'list-plugins', 'list-types', 'config=', 'value=', 'list-config', 'force-new'])
    except Exception as err:
        print("Error: "+str(err)+", Try --help for usage\n\n")
        usage()
        sys.exit(2)

    Type = None
    Variable = None
    ForceNew = False

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit(2)

        if o in ('-p', '--list-plugins', '--list-types'):
            files = os.listdir(libnbnotify.plugins.__path__[0])

            print("Avaliable plugins:")

            for file in files:
                if file[-4:] == ".pyc":
                    continue

                if file == "__init__.py":
                    continue

                print("+ "+file[:-3])

            sys.exit(0)

        # CONFIG EDITOR
        if o in "--config":
            Variable = a

        if o in "--force-new":
            ForceNew = True

        if o in "--value":
            if Variable == None:
                print("You must specify --config=section:option first")
                sys.exit(0)

            Var = Variable.split(":")

            if len(Var) == 2:
                if str(app.configGetKey(Var[0], Var[1])) != "False" or ForceNew == True:
                    app.configSetKey(Var[0], Var[1], a)
                    print(Var[0] + ":"+Var[1]+" = "+a)
                    app.saveConfiguration()
                else:
                    print(Var[0] + ":"+Var[1]+" does not exists in config file, use --force-new to force creation of new variable.")

            sys.exit(0)     

        if o in ('-l', '--list'):
            links = app.configGetSection('links')

            if links == False:
                print("No links in database.")
                sys.exit(0)

            for link in links:
                print(links[link])

            sys.exit(0)   

        if o in "--list-config":
            i = 0

            for var in app.Config:
                i = i + 1
                section = app.configGetSection(var)

                print(str(i)+". "+str(var))
                for option in section:
                    print("==> "+option+" = "+str(app.configGetKey(var, option))+";")

                print("\n")

            sys.exit(0)


        if o in ('-t', '--type'):
            Type = a

        if o in ('-a', '--append'):
            app.configSetKey('links', hashlib.md5(a).hexdigest(), a)

            if not Type == None:
                if os.path.isfile(libnbnotify.plugins.__path__[0]+"/"+Type+".py"):
                    app.configSetKey('linktypes', hashlib.md5(a).hexdigest(), Type)
                    print("Type changed to \""+str(Type)+"\" for link: "+str(a))
                else:
                    print("Invalid type "+a+" - does not exists in plugins list.")

            app.saveConfiguration()
            sys.exit(0)

        if o in ('-r', '--remove'):
            links = app.configGetSection('links')

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
                app.saveConfiguration()
            else:
                print("Link not found, nothing changed.")

            sys.exit(0)

        if o in '--daemonize':
            daemonize()


    app.doPluginsLoad()
    app.main()

def usage():
    print("nbnotify -[short GNU option] [value] --[long GNU option]=[value]")
    print("\nUsage:\n")
    print("--help, -h (this message)")
    print("--type, -t (type of added link; MUST BE USED BEFORE --add)")
    print("--append, -a (add or modify link in database)")
    print("--remove, -r (remove link from database)")
    print("--list, -l (list all links)")
    print("--list-plugins, --list-types, -p (list all avaliable plugins)")
    print("--list-config, (list all avaliable configuration variables)")
    print("--daemonize, (fork to background and run as userspace daemon)")
    print("--config, (set configuration variable)")
    print("--value, (set value of configuration variable specified in --config)")
    print("--force-new (force creation of new configuration variable)")

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

app = libnbnotify.main.nbnotify()
parseArgs(app)
