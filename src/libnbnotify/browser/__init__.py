import datetime

class nbCookie:
    array = dict()

    def __init__(self, array):
        self.array = array

    def toCookieHeader(self):
        """ Return cookies in client header format - Cookie """

        cookiesString = ""

        for result in self.array:
            cookiesString += result['name']+'='+str(result['value'])+'; '

        return cookiesString

    def toSetCookieHeader(self):
        """ Returns cookies in server header format - SetCookie """

        cookies = list()

        for cookie in self.array:
            # name and value (required basics)
            cookieString = cookie['name']+"="+cookie['value']+"; "

            # expires
            if cookie['expires'] != None:
                cookieString += "Expires="+datetime.datetime.fromtimestamp(cookie['expires']).strftime('%a, %d-%b-%Y %H:%M:%S')+" GMT; "

            # path
            cookieString += "path="+cookie['path']+"; "

            cookies.append(cookieString)

        return cookies

    def toArray(self):
        return self.array
