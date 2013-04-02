#!/usr/bin/env python
#
# ldaptools.py
#
# Take list of groups from AD and generate users for puppet.
#

import ldap
import pickle
import getopt, sys

def usage():
    print """
Usage: ldapsync.py [-hvd]
"""

def dprint(msg):
    try:
        if debug:
            print("  DEBUG: %s" % msg)
    except NameError:
        pass

def vprint(msg):
    try:
        if verbose:
            print("  %s" % msg)
    except NameError:
        pass

try:
    (opts, args) = getopt.getopt(sys.argv[1:], "hvd", ["help", "verbose", "debug"])
except getopt.GetoptError:
    usage()
    sys.exit(2)

# Option handling variables
verbose = 0
debug = 0

for o, a in opts:
    if o in ("-v", "--verbose"):
        verbose = 1
    if o in ("-d", "--debug"):
        debug = 1
    if o in ("-h", "--help"):
        usage()
        sys.exit(0)

if len(args) > 0:
    usage()
    sys.exit(2)

virtualfile='../manifests/virtual.pp'
deletefile='../manifests/delete.pp'
groupdir='../manifests/ad/'
allgroupfile=groupdir+'allgroups.pp'
datafile='../data/userlist.dat'
ldapurl='ldap://ad.contoso.com/'
user_dn='ServiceAccount@contoso.com'
user_pw='s00persekritp4ssw0rd'
basedn='dc=contoso,dc=com'
grouplist=[ 
    'Developers', 
    'Linux-Admins', 
    'Shell-Users'  ]

modeledgids=[]
modeleduids=[]
modeleduserdata={}

#
# get list of users for a group
#
def grabusersgroup(searchgroup):
    base_dn='ou=Groups,dc=contoso,dc=com'
    attrs = ['member']
    filter="cn="+searchgroup
    try:
        dprint("Grabbing users from %s" % searchgroup)
        groupvar = con.search_s(base_dn, ldap.SCOPE_SUBTREE, filter, attrs )
        userlist = []

        #dprint("Group %s has %i" % (searchgroup, len(groupvar[0][1]['member'])))
        for x in groupvar[0][1]['member']:
            user=x.split(',')[0].split('=')[1]
            dprint("Adding %s to %s" % (user, searchgroup))
            if 'CN='+user+',OU=People,DC=contoso,DC=com' == x:
                userlist.append(user)
                userlist.sort()
            elif 'OU=Groups' in x:  ## Recursively call grabusers on group name
                nestedgroup=x.split(',')[0].split('=')[1]
                dprint(" Recursing:  %s => %s" % (searchgroup, nestedgroup))
                nestedusers = grabusersgroup(nestedgroup)
                dprint(nestedusers)
                if nestedusers == -1:
                    dprint("%s is an empty group" % nestedgroup)
                    continue
                dprint(" %s   contains:  %s" % (nestedgroup, nestedusers))
                dprint(nestedusers)
                for user in nestedusers:
                    if not user in userlist:
                        userlist.append(user)
                        userlist.sort()                    
        return set(userlist)
    except:
        dprint("Unexpected error for group %s: %s" % (searchgroup, sys.exc_info()))
        return -1


#
# get groups from user ensuring current group
def getusergroups(memberoflist,currentgroup):
    grouplist=[]
    for group in memberoflist:
      try:
          results = dumpgroup(group.split(',')[0].split('=')[1])
          grouplist.append(results[0][1]['msSFU30Name'][0])
          dprint(results)
      except:
          dprint(results)
          dprint(sys.exc_info())
          continue
    if currentgroup not in grouplist:
      grouplist.append(currentgroup)
    return grouplist


#
# return a string from a group list in puppet format
def formatgrouplist(grouplist):
    groupstring="["
    for group in grouplist:
      groupstring+=' "'+group+'",'
    groupstring+="]"
    dprint("Groupstring: "+groupstring)
    return groupstring

      

def printobject(results):
    print "Printing attributes for: "
    # print user followed by key/value pairs
    try:
      print results[0][0]
      for key,val in results[0][1].iteritems():
        print "\t"+key+": "+str(val)
    except IndexError:
      print "!! User not found!\n"
      clean_exit()
      sys.exit()

#
# dump user with desired attributes, returns result
def dumpuser(user):
    userattrs=['uidNumber','gidNumber','msSFU30Name','msSFU30NisDomain','unixHomeDirectory','loginShell','givenName','sn', 'memberOf']
    search_dn='ou=People,'+basedn
    filter="cn="+user
    results = con.search_s(search_dn, ldap.SCOPE_SUBTREE, filter, userattrs )
    return results

#
# dump group with desired attributes, returns result
def dumpgroup(group):
    groupattrs=['gidNumber','msSFU30Name','msSFU30NisDomain']
    search_dn="ou=Groups,"+basedn
    filter="cn="+group
    results = con.search_s(search_dn, ldap.SCOPE_SUBTREE, filter, groupattrs )
    #dprint(results)
    return results


# cause ldap module to show verbose info if we are, disabled since very verbose
if debug:
    #con = ldap.initialize(ldapurl,2)
    con = ldap.initialize(ldapurl)
else:
    con = ldap.initialize(ldapurl)
con.set_option(ldap.OPT_X_TLS_DEMAND, True)
con.start_tls_s()
try: 
    con.bind_s(user_dn, user_pw)
except ldap.INVALID_CREDENTIALS:
    print "Your username or password is incorrect."
    sys.exit()
except ldap.LDAPError, e:
    if type(e.message) == dict and e.message.has_key('desc'):
            print e.message['desc']
    else: 
            print e
    sys.exit()

# write puppet files
virtualf = open(virtualfile, 'w')
deletef = open(deletefile, 'w')
allgroupf = open(allgroupfile, 'w')
try:
    dataf = open(datafile, 'r+')
    existingusers = pickle.load(dataf)
    dprint('Loading data from: '+datafile+'\n')
    dataf.close()
except:
    sys.exit()
remainingusers=existingusers[:]

#
# write file headers
#
print("Creating virtusers.pp")
virtualf.write('''# %s
#
# This file is NOT to be edited. It is generated by a sync with AD.
#
# See modules/user/scripts/ldapsync.py
#

class user::virtual {
  include 'user::delete'

  group {
    "POSIX-Users" :
      ensure => present,
      gid => 2000;
  }
''' % virtualfile)

print("Creating allgroups.pp")
allgroupf.write('''# %s
#
# This file is NOT to be edited. It is generated by a sync with AD.
#
# See modules/user/scripts/ldapsync.py
#
class user::ad::allgroups {
''' % allgroupfile)

# first pass of groups creates allgroups class
for group in sorted(grouplist):
  allgroupf.write("  include 'user::ad::%s'\n" % group.lower())
allgroupf.write("}\n\n")
allgroupf.close()


print("Iterating groups")
# Iterate through groups listed above
for group in sorted(grouplist):
    dprint("Processing group %s" % group)
    dprint(modeleduserdata.keys())
    # this is just for some feedback
    if not debug and not verbose:
      sys.stdout.write('.')
      sys.stdout.flush()

    # Try to get group attributes, and skip group if missing
    try:
        groupattrs=dumpgroup(group)
        dprint(groupattrs)
        groupid=groupattrs[0][1]['gidNumber'][0]
        if groupid in modeledgids:
            vprint('%s => FAILURE: Duplicate GID %s' % (group, groupid))
            continue
        else:
            modeledgids.append(groupid)
    except:
        # this is probably bad so should generate its own error
        sys.stderr.write('\n%s => FAILURE: Missing Attributes\n' % (group))
        continue
    groupf = open(groupdir+group.lower()+'.pp', 'w')
    groupf.write( '''#
#
# This file is NOT to be edited. It is generated by a sync with AD.
#
# See modules/user/scripts/ldapsync.py
#
class user::ad::%s {
  include 'user::virtual'
  include 'auth::local'
  
''' % ( group.lower() ))
    virtualf.write('''  group {
    "%s" :
      ensure => present,
      gid => %s;
  }
''' % ( group, groupid ))
    vprint('%s => %s' % (group, groupid))

    try:
      # Process users from the group
      for user in grabusersgroup(group):
          # keep track of every user ever seen, for deletion
          if not user in existingusers:
              existingusers.append(user)
              vprint("%s missing from existingusers" % user)
          # catch exceptions for LDAP errors
          try:
              dprint("Adding %s to modeled users" % user)
              modeleduserdata.keys().append(user)
              # fetch user attributes
              userattrs=dumpuser(user)

              # check if valid account - can be changed to isdisjointed in 2.6
              if len(set(userattrs[0][1]['memberOf']).intersection(validaccountgroups)) < 1:
                  vprint('  %s => FAILURE: Invalid Account' % user)
                  continue

              if user in modeleduserdata.keys():
                  modeleduserdata[user]['groups'].append(group)
              else:
                  modeleduserdata[user]={}
                  # collect user attributes
                  modeleduserdata[user]['uid']=userattrs[0][1]['uidNumber'][0]
                  modeleduserdata[user]['gid']=userattrs[0][1]['gidNumber'][0]
                  modeleduserdata[user]['home']=userattrs[0][1]['unixHomeDirectory'][0]
                  modeleduserdata[user]['shell']=userattrs[0][1]['loginShell'][0]
                  modeleduserdata[user]['comment']=str(userattrs[0][1]['givenName'][0])+' '+str(userattrs[0][1]['sn'][0])
                  # grab groups
                  modeleduserdata[user]['groups']=getusergroups(userattrs[0][1]['memberOf'],group)

                  # avoid duplicate uids
                  if modeleduserdata[user]['uid'] in modeleduids:
                      vprint('  %s => FAILURE: Duplicate UID %s' % (user, modeleduserdata[user]['uid']))
                      del modeleduserdata[user]
                      continue
                  else:
                      modeleduids.append(modeleduserdata[user]['uid'])
          except:
              try:
                  remainingusers.remove(user)
              except:
                  pass
              vprint('  %s => FAILURE: Missing Attributes' % (user))
              del modeleduserdata[user]
              #raise
              continue
          # continue for user and write them to the groupfile
          groupf.write("  realize( User['"+user+"'] )\n")
          dprint(userattrs)
          if user in remainingusers:
              try: 
                  remainingusers.remove(user)
              except:
                  pass
    except TypeError:
      groupf.write('}\n\n')
      continue
    groupf.write('}\n\n')
    groupf.close()

dprint( sorted(modeleduserdata.keys()))

# write out the virtual users
print('')
print("Iterating found users")
for user in sorted(modeleduserdata.keys()):
    if not debug and not verbose:
      sys.stdout.write('.')
      sys.stdout.flush()
    vprint('  %s => %s' % (user, modeleduserdata[user]['uid']))
    virtualf.write( '''  @user {
    "%s" :
      ensure => present,
      uid => %s,
      gid => %s,
      groups => %s,
      home => "%s",
      comment => "%s",
      managehome => true,
      shell => "%s",
      require => Group["POSIX-Users"];
  }
''' % (user, modeleduserdata[user]['uid'], modeleduserdata[user]['gid'], formatgrouplist(modeleduserdata[user]['groups']), modeleduserdata[user]['home'], modeleduserdata[user]['comment'], modeleduserdata[user]['shell']) )

virtualf.write('}\n')

print("Creating delete.pp")
deletef.write('''# %s
#
# This file is NOT to be edited. It is generated by a sync with AD.
#
# See modules/user/scripts/ldapsync.py
#

''' % deletefile)
#remove old users
print('')
print("Iterating lost users for deletion")
deletef.write( 'class user::delete {\n' )
remainingusers.sort()
deletef.write('  user {\n')
for user in remainingusers:
    deletef.write( '''    '%s' :
      ensure => absent;
''' % user )
    vprint('DELETE  %s' % user)
deletef.write('  }\n')
deletef.write('}\n')

#close the shop up
print("Cleaning up and closing")
dataf = open(datafile, 'w')
pickle.dump(existingusers,dataf)
dataf.close()
virtualf.close()
deletef.close()
con.unbind()
