#!/usr/bin/env python
import libnbnotify.browser.chromium as chromium

print("Initializing Chromium browser support...")
browser = chromium.nbBrowser()
print("Getting list of browser profiles...")
print(browser.listProfiles())
print("Loading browser cookies... ["+str(browser.load("default"))+"]")
print("facebook.com cookies:")
print(browser.getCookie("facebook.com").toCookieHeader())
