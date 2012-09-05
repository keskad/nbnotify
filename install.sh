#!/usr/bin/env bash
cp dpnotify.py /usr/bin/dpnotify
cp ./usr / -r
./setup.py install
chown root /usr/share/dpnotify -R
chown root /usr/bin/dpnotify
chmod +x /usr/bin/dpnotify
echo "dpnotify installed."
