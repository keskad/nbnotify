#!/usr/bin/env python
#-*- coding: utf-8 -*-
import libnbnotify.main, libnbnotify.database, os, sys, getopt, hashlib

def parseArgs(app):
    """ Args parser """

    if not os.path.isdir(app.iconCacheDir):
        os.system("mkdir -p "+app.iconCacheDir)

    app.db = libnbnotify.database.Database()
    app.loadConfig()

    try:
        opts, args = getopt.getopt(sys.argv[1:], "ha:r:l", ["help", "add=", "remove=", 'list', 'daemonize'])
    except Exception as err:
        print("Error: "+str(err)+", Try --help for usage\n\n")
        usage()
        sys.exit(2)

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit(2)

        if o in ('-a', '--add'):
            app.configSetKey('links', hashlib.md5(a).hexdigest(), a)
            app.saveConfiguration()
            sys.exit(0)

        if o in ('-l', '--list'):
            links = app.configGetSection('links')

            if links == False:
                print("No links in database.")
                sys.exit(0)

            for link in links:
                print(links[link])

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

app = libnbnotify.main.nbnotify()
parseArgs(app)
