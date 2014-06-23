#!/usr/bin/python
#
# TODO: more error checking, right now it's mostly relying on python exceptions
#       password on command line not the best, needs to be in config file or other method
#
#
# dxr 23 05 2014
#
# V1.2
#
# need to delete the lock file if it fails with an exception 
#
# ideas from http://yuji.wordpress.com/2011/06/22/python-imaplib-imap-example-with-gmail/
#

import imaplib, socket, syslog, ConfigParser

import email, mailbox, smtplib, lockfile, sys, argparse, html2text, copy


#
# parse command line args
#

parser = argparse.ArgumentParser(description='transfer email from imap account to SMTP server with different recipient, preserving sender')

parser.add_argument("--from_account",
    help="account name of imap account, expect something like DOMAIN\ABC or abc@domain.com, might need to escape the '\\', i.e. use \\\\ with command line use ")
parser.add_argument("--imap_server",
    help="imap server we connect to to fetch and then delete the mail. currently need a source code change for imaps")
parser.add_argument("--from_password",
    help="password of imap account to connect to")
parser.add_argument("--to_smtp_server",
    help="smtp server to send fetched emails from")
parser.add_argument("--to_address",
    help="email address to send the fetched emails to")
parser.add_argument("--verbose",
    help="increase output verbosity",action='store_true')
parser.add_argument("--fixemail",
    help="try and convert html emails with no text to text to work better with wonderdesk",action='store_true')
parser.add_argument("--syslog",
    help="log basic status info to syslog",action='store_true')
parser.add_argument("--config",
    help="config file, will override any command line options")
parser.add_argument("--lockfile",
    help="lock file, so only one instance of this program with this config can run ",default="/tmp/imap2smtp.lock")

args = parser.parse_args()

#
# if we have had a config file specified, parse it, and override any command line args..
#

if args.config:
   if args.verbose:
      print "config file: ",args.config
   settings = ConfigParser.ConfigParser()
   settings.read(args.config)
   if len(settings.sections()) != 1:
      print "error: config file doesn't have just one [section], exiting!"
      sys.exit(1)
   thesection = settings.sections()[0]
   if settings.has_option(thesection,'imap_server'):
      args.imap_server = settings.get(thesection,'imap_server')
   if settings.has_option(thesection,'from_account'):
      args.from_account = settings.get(thesection,'from_account')
   if settings.has_option(thesection,'from_password'):
      args.from_password = settings.get(thesection,'from_password')
   if settings.has_option(thesection,'to_smtp_server'):
      args.to_smtp_server = settings.get(thesection,'to_smtp_server')
   if settings.has_option(thesection,'to_address'):
      args.to_address = settings.get(thesection,'to_address')
   if settings.has_option(thesection,'verbose'):
      args.verbose = settings.getboolean(thesection,'verbose')
   if settings.has_option(thesection,'syslog'):
      args.syslog = settings.getboolean(thesection,'syslog')
   if settings.has_option(thesection,'fixemail'):
      args.fixemail = settings.getboolean(thesection,'fixemail')
   if settings.has_option(thesection,'lockfile'):
      args.lockfile = settings.get(thesection,'lockfile')

   if settings.has_option(thesection,'timeout'):
      socket.setdefaulttimeout(settings.getint(thesection,'timeout'))

if args.verbose:
    print "verbose mode on"
    if args.syslog:
       print "also logging to syslog"
    if args.fixemail:
       print "also fixing, HTML to text in email body"

lock = lockfile.FileLock(args.lockfile)

if lock.is_locked():
   print "imap2smtp process already running so exit"
   sys.exit(0)

lock.acquire()

if args.verbose:
   print "connecting with account: ",args.from_account

try:
   # if we want SSL....
   # mail = imaplib.IMAP4_SSL(args.imap_server)

   mail = imaplib.IMAP4(args.imap_server)
   mail.login(args.from_account,args.from_password)
except socket.gaierror, e:
   print "trying to connect to imap server %s .. Address-related error connecting to server: %s" % (args.imap_server,e)
   lock.release()
   sys.exit(1)
except socket.error, e:
   print "trying to connect to imap server %s.. Connection error: %s" % (args.imap_server,e)
   lock.release()
   sys.exit(1)
except imaplib.IMAP4.error, e:
   print "trying to connect to imap server %s.. IMAP error: %s" % (args.imap_server,e)
   lock.release()
   sys.exit(1)

if args.verbose:
    print "connected to %s with IMAP4, user account %s " % (args.imap_server, args.from_account)

mail.select("inbox") # connect to inbox.

result, data = mail.uid('search', None, "ALL")
uidlist = data[0].split()

if args.verbose:
   print len(uidlist), " incoming emails pending..."

for searchedemailid in uidlist:
   result, data = mail.uid('fetch',searchedemailid, "(RFC822)")
   raw_email = data[0][1]
   emailmessage = email.message_from_string(raw_email)
   sender  = emailmessage['From']
   if args.syslog:
      syslog.syslog('message fetched with sender: '+sender)
   if args.verbose:
      print "   message fetched, sender is ",sender
      print " is_multipart()", emailmessage.is_multipart()

   if args.fixemail:
      if args.verbose:
         print "fixing html only, if we are need to...."
      hastextplain = False
      hastexthtml = True
      haveconverted = False
      # walk the email parts... if it is not multipart we only get one thing to walk, so we do it
      # anyway.
      for part in emailmessage.walk():
         if part.get_content_type() == 'text/plain':
            if args.verbose:
               print "found plain text part"
            hastextplain = True
         if part.get_content_type() == 'text/html':
            if args.verbose:
               print "found htlm part, so lets convert it to text if we havent already.."
            if not haveconverted:
               # only want to convert the first HTML component...
               textofhtml = html2text.html2text(part.get_payload()).replace('&nbsp_place_holder;', ' ')
               haveconverted = True

      if not hastextplain and hastexthtml:
         # if we didnt find a plain text part, but DID find a html part,
         # add the converted HTML of the first HTML part
         # newpayload = email.mime.Text.MIMEText(textofhtml, 'plain')
         newpayload = email.mime.Text.MIMEText(textofhtml.encode('utf-8'), 'plain', 'utf-8')
         if not emailmessage.is_multipart():
            if args.verbose:
               print "not a multipart email so replacing body with text conversion of the html"
            if args.syslog:
               syslog.syslog('modifying email, replacing html with text')
            emailmessage.set_payload(textofhtml.encode('utf-8'))
         else:
            # hopefully this adds the text conversion as the first element so
            # WD sees it first....
            if args.verbose:
               print "this is a multipart, so we add a text conversion as the first part of the multipart"
            if args.syslog:
               syslog.syslog('modifying multipart email, adding text conversion to start')
            emailmessage.set_payload([newpayload]+emailmessage.get_payload())
         raw_email = emailmessage.as_string()
         if args.verbose:
            print "newly rewritten raw_email is:"
            print "----------------"
            print raw_email
            print "----------------"

   # send as email From: the sender we extracted...
   smtpObj = smtplib.SMTP(args.to_smtp_server)
   smtpObj.sendmail(sender, [args.to_address], raw_email)
   if args.verbose:
      print "   sent via smtp to ",args.to_smtp_server
   if args.syslog:
      syslog.syslog("   sent via smtp to "+args.to_smtp_server)

   # if we got past sending the email ok... then delete it..
   mail.uid('STORE',searchedemailid, '+FLAGS', '(\\Deleted)')
   if args.verbose:
      print "   marked as deleted "

mail.expunge()
if args.verbose:
   print "imap expunge of deleted emails"
mail.close()
lock.release()
if args.verbose:
   print "imap closed and lock file released."
