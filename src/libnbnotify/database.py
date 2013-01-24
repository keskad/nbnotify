import sys, sqlite3, os

class MySum:
    """ Counting results class for SQLite3 """

    def __init__(self):
        self.count = 0

    def step(self, value):
        self.count += value

    def finalize(self):
        return self.count

class Database:
    """ Simple SQLite3 database support """

    socket = None
    cursor = None
    dbPath = os.path.expanduser("~/.nbnotify/db_cache.sqlite3")

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
        else:
            try:
                sql = self.cursor.execute("SELECT `value` FROM `nb_meta` WHERE `key`='db_version';")
            except sqlite3.OperationalError:
                os.remove(self.dbPath)
                self.__init__()
            

    def query(self, query):
        return self.cursor.execute(query)

    def createEmptyDB(self):
        print("Creating new database...")
        self.cursor.execute("CREATE TABLE `nb_meta` (key varchar(64) primary key, value varchar(1024));")
        self.cursor.execute("INSERT INTO `nb_meta` (key, value) VALUES ('db_version', '2');")

        # sid = unique id based on md5 sum of notification content, date and pageID
        self.cursor.execute("CREATE TABLE `nb_notifications` (sid varchar(80) primary key, date varchar(40), title varchar(120), content varchar(1024), icon varchar(1024), pageID int(20));")
        self.socket.commit()





