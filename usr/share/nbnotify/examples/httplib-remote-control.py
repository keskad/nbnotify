#!/usr/bin/env python
import httplib
import json

class nbnotifyClient:
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}

    def __init__(self, ip):
        self.connection = httplib.HTTPConnection(ip, 9954)

    def request(self, jsonData):
        self.connection.request("POST", "/", jsonData, self.headers)
        return self.connection.getresponse()


client = nbnotifyClient("192.168.1.102")
print('Sending ping: {"function": "ping", "data": ""}')
print("=> Response: "+client.request('{"function": "ping", "data": ""}').read())
print('')


print('Sending configGetKey: {"function": "configGetKey", "data": {"section": "global", "key": "checktime"}}')
response = client.request('{"function": "configGetKey", "data": {"section": "global", "key": "checktime"}}').read()
print("=> Response: "+response)
print("Check time is "+json.loads(response)['response'])
print('')


print('Getting all links from database...')
response = client.request('{"function": "getAllEntries", "data": ""}').read()
data = json.loads(response)

k = json.loads(data['response'].replace("'", '"'))

for link in k:
    print(link + " => " + k[link])

print('')


print('Sending unknown command:')
response = client.request('{"function": "thisFunctionWillNotBeImplemented", "data": ""}').read()
print("=> Response: "+response)

print('')


print('Sending forbidden command:')
response = client.request('{"function": "__init__", "data": ""}').read()
print("=> Response: "+response)
