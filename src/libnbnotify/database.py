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
