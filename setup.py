#!/usr/bin/env python
from distutils.core import setup

setup(name='nbnotify',
      version='0.1',
      package_dir={'': 'src'},      
      packages=['libnbnotify', 'libnbnotify.plugins']
     )
