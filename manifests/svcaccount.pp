# This file contains the UNIX users and groups that do not map to Active Directory objects.
class user::svcaccount {
  @group {
    "mock":
      ensure => present,
      gid => '500';
    "svn":
      ensure => present,
      gid => 501;
  }
  @user {
    "rpmbuild" :
      ensure => present,
      uid => 2003,
      gid => 100,
      groups => ["mock"],
      home => '/home/rpmbuild',
      comment => 'RPM Builder',
      managehome => true,
      require => Group['mock'];
    "svn" :
      ensure => present,
      uid => 2037,
      gid => "svn",
      comment => "SVN User",
      managehome => true,
      require => Group["svn"];
}
