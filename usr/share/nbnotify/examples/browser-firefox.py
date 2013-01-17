#!/usr/bin/env python
import libnbnotify.browser.firefox as firefox

print("Initializing Firefox browser support...")
browser = firefox.nbBrowser()
print("Getting list of browser profiles...")
print(browser.listProfiles())
print("Loading browser cookies... ["+str(browser.load("default"))+"]")
print("facebook.com cookies:")
print(browser.getCookie("facebook.com").toCookieHeader())
