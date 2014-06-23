
A simple script to download email from the inbox of a remote IMAP server.
It then sends it to a specified smtp server and destination email, preserving the sender.
There is an option to convert the first HTML part of a multipart email to text, or if a single part
email replace the whole HTML body with the converted text.
This was made to work around the quirks of both an outsourced email provider and some older helpdesk software.

In a Debian/Ubuntu type operating system the following modules may need to be installed:

```
apt-get install python-argparse
apt-get install python-html2text
apt-get install python-argparse
```

tested on Python 2.6.5 and Python 2.7.3

All config options can be specified on the command line, or in a config file.

The config file uses the python .ini syntax of:
```
[anything]
imap_server = imap.com
from_account = fred
from_password = xxxpasswordxxx
to_smtp_server = mail.com
to_address = bill@mail.com
syslog = Yes
verbose = No
fixemailforwd = Yes
lockfile = /tmp/this_is_a.lock
optional TCP timeout in seconds
timeout = 15
```

but there should only be one section and the name of the section doesnt matter.


