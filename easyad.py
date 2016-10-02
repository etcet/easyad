# -*- coding: utf-8 -*-

"""
A simple Python module for common Active Directory authentication and lookup tasks
"""

from __future__ import unicode_literals, print_function

from base64 import b64encode
from datetime import datetime, timedelta

import ldap
from ldap.filter import escape_filter_chars

"""Copyright 2016 Sean Whalen

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""


__version__ = "0.5.0"


# Python 2 & 3 support hack
try:
    unicode
except NameError:
    unicode = str


def convert_ad_timestamp(timestamp, json_safe=False, str_format="%x %X"):
    """
    Converts a LDAP timestamp to a datetime or a human-readable string
    Args:
        timestamp: the LDAP timestamp
        json_safe: If true, return a a human-readable string instead of a datetime
        str_format: The string format to use if json_safe is true

    Returns:
        A datetime or a human-readable string
    """
    timestamp = int(timestamp)
    if timestamp == 0:
        return None
    epoch_start = datetime(year=1601, month=1, day=1)
    seconds_since_epoch = timestamp / 10 ** 7
    converted_timestamp = epoch_start + timedelta(seconds=seconds_since_epoch)

    if json_safe:
        converted_timestamp = converted_timestamp.strftime(str_format)

    return converted_timestamp


def _get_last_logon(timestamp, json_safe=False):
    """
    Converts a LastLogonTimestamp to a datetime or human-readable format
    Args:
        timestamp: The timestamp from a lastLogonTimestamp user attribute
        json_safe: If true, always return a string

    Returns:
        A datetime or string showing the user's last login, or the string "<=14", since
        lastLogonTimestamp is not accurate withing 14 days
    """
    timestamp = convert_ad_timestamp(timestamp, json_safe=False)
    if timestamp is None:
        return -1
    delta = datetime.now() - timestamp
    days = delta.days

    # LastLogonTimestamp is not accurate beyond 14 days
    if days <= 14:
        timestamp = "<= 14 days"
    elif json_safe:
        timestamp.strftime("%x %X")

    return timestamp


def decode_ldap_results(results, json_safe=False):
    """
    Converts LDAP search results from bytes to a dictionary of UTF-8 where possible

    Args:
        results: LDAP search results
        json_safe: If true, convert binary data to base64 and datetimes to human-readable strings

    Returns:
        A list of processed LDAP result dictionaries.
    """
    results = [entry for dn, entry in results if isinstance(entry, dict)]
    for ldap_object in results:
        for attribute in ldap_object.keys():
            # pyldap returns all attributes as bytes. Yuk!
            for i in range(len(ldap_object[attribute])):
                try:
                    ldap_object[attribute][i] = ldap_object[attribute][i].decode("UTF-8")
                except ValueError:
                    if json_safe:
                        ldap_object[attribute][i] = b64encode(ldap_object[attribute][i]).decode("UTF-8")
            if len(ldap_object[attribute]) == 1:
                ldap_object[attribute] = ldap_object[attribute][0]

    return results


class ADConnection(object):
    """
    A LDAP configuration abstraction

    Attributes:
        config: The configuration dictionary
        ad: The LDAP interface instance
    """
    def __init__(self, config):
        self.config = config
        ad_server_url = "ldap://{0}".format(self.config["AD_SERVER"])
        ad = ldap.initialize(ad_server_url)
        ad.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)
        ad.set_option(ldap.OPT_REFERRALS, 0)

        if "AD_CA_CERT_FILE" in self.config and self.config["AD_CA_CERT_FILE"]:
            ad.set_option(ldap.OPT_X_TLS_CACERTFILE, self.config["AD_CA_CERT_FILE"])  # The root CA certificate
        if "AD_REQUIRE_TLS" in self.config and not self.config["AD_REQUIRE_TLS"]:
            ad.set_option(ldap.OPT_X_TLS_DEMAND, 0)
        else:
            ad.set_option(ldap.OPT_X_TLS_DEMAND, 1)  # Force TLS by default

        self.ad = ad

    def bind(self, credentials=None):
        """
        Attempts to bind to the Active Directory server

        Args:
            credentials: A optional dictionary of the username and password to use.
            If credentials are not passed, the credentials from the initial EasyAD configuration are used.

        Returns:
            True if the bind was successful

        Raises:
            ldap.LDAP_ERROR
        """
        if credentials is None or "username" not in credentials or "password" not in credentials:
            if "AD_BIND_USERNAME" not in self.config or self.config["AD_BIND_USERNAME"] is None:
                raise ValueError("AD_BIND_USERNAME must be set")
            if "AD_BIND_PASSWORD" not in self.config or self.config["AD_BIND_PASSWORD"] is None:
                raise ValueError("AD_BIND_PASSWORD must be set")

            credentials = dict()
            credentials["username"] = self.config["AD_BIND_USERNAME"]
            credentials["password"] = self.config["AD_BIND_PASSWORD"]

        username = credentials["username"].split("\\")[-1]
        if "@" not in username and "cn=" not in username.lower():
            username = "{0}@{1}".format(username, self.config["AD_DOMAIN"])

        password = credentials["password"]

        self.ad.bind_s(username, password)
        return True

    def unbind(self):
        """
        Unbind from the Active Directory server
        """
        self.ad.unbind()


class EasyAD(object):
    """
    A simple class for interacting with Active Directory

    Attributes:
        user_attributes: A default list of attributes to return from a user query
        group_attributes: A default list of attributes to return from a user query
    """
    user_attributes = [
        "businessCategory",
        "businessSegment",
        "businessSegmentDescription",
        "businessUnitDescription"
        "c",
        "cn",
        "co",
        "company",
        "costCenter",
        "countryCode",
        "department",
        "departmentNumber",
        "displayName",
        "distinguishedName",
        "employeeClass",
        "employeeNumber",
        "employeeStatus",
        "employeeType",
        "enterpriseBusinessUnitDescription",
        "givenName",
        "hireDate",
        "homeDirectory",
        "homeDrive",
        "iamFullName",
        "ipPhone",
        "jobFamilyDescription",
        "jobFunctionDescription",
        "jobTrack",
        "l",
        "LastLogonTimestamp",
        "lockoutTime",
        "mail",
        "mailNickname",
        "manager",
        "memberOf",
        "phonebookVisibility",
        "physicalDeliveryOfficeName",
        "postalCode",
        "prefFirstName",
        "pwdLastSet",
        "rehireDate",
        "roomNumber",
        "sAMAccountName",
        "scriptPath",
        "showInAddressBook",
        "siteCode",
        "siteName",
        "sn",
        "st",
        "streetAddress",
        "telephoneNumber",
        "thumbnailPhoto",
        "title",
        "uid",
        "userAccountControl",
        "userPrincipalName"
    ]

    group_attributes = [
        "cn",
        "distinguishedName",
        "managedBy",
        "member",
        "name"
    ]

    # Another python 2 support hack
    user_attributes = list(map(lambda x: str(x), user_attributes))
    group_attributes = list(map(lambda x: str(x), group_attributes))

    def __init__(self, config):
        """
        Initializes the EasyAD object

        Args:
            config: A dictionary of configuration settings
                Required:
                    AD_SERVER: The hostname of the Active Directory Server
                    AD_DOMAIN: The domain to bind to, in TLD format
                Optional:
                    AD_REQUIRE_TLS: Require a TLS connection. True by default.
                    AD_CA_CERT_FILE: The path to the root CA certificate file
                    AD_BASE_DN: Overrides the base distinguished name. Derived from AD_DOMAIN by default.
        """
        self.config = config
        base_dn = ""
        for part in self.config["AD_DOMAIN"].split("."):
            base_dn += "dc={0},".format(part)
        base_dn = base_dn.rstrip(",")
        if "AD_BASE_DN" not in self.config.keys() or self.config["BASE_DN"] is None:
            self.config["AD_BASE_DN"] = base_dn
        self.user_attributes = EasyAD.user_attributes
        self.group_attributes = EasyAD.group_attributes

    def get_user(self, user_string, base=None, credentials=None, attributes=None, json_safe=False):
        """
        Searches for a unique user object and returns its attributes

        Args:
            user_string: A userPrincipalName, sAMAccountName, or distinguishedName
            base: Optionally override the base dn
            credentials: A optional dictionary of the username and password to use.
            If credentials are not passed, the credentials from the initial EasyAD configuration are used.
            attributes: An optional list of attributes to return. Otherwise uses self.user_attributes.
            To return all attributes, pass an empty list.
            json_safe: If true, convert binary data to base64 and datetimes to human-readable strings

        Returns:
            A dictionary of user attributes

        Raises:
            ValueError: Query returned no or multiple results

        Raises:
            ldap.LDAP_ERROR
        """
        if base is None:
            base = self.config["AD_BASE_DN"]

        if attributes is None:
            attributes = self.user_attributes

        filter_string = "(&(objectClass=user)(|(userPrincipalName={0})(sAMAccountName={0})(mail={0})" \
                        "(distinguishedName={0})))".format(escape_filter_chars(user_string))
        connection = ADConnection(self.config)

        try:
            connection.bind(credentials)
            results = connection.ad.search_s(base=base,
                                             scope=ldap.SCOPE_SUBTREE,
                                             filterstr=filter_string,
                                             attrlist=attributes)

            results = decode_ldap_results(results, json_safe=json_safe)

            if len(results) == 0:
                raise ValueError("No such user")
            elif len(results) > 1:
                raise ValueError("The query returned more than one result")

            user = results[0]

            if "memberOf" in user.keys():
                user["memberOf"] = sorted(user["memberOf"], key=lambda dn: dn.lower())
            if "showInAddressBook" in user.keys():
                user["showInAddressBook"] = sorted(user["showInAddressBook"], key=lambda dn: dn.lower())
            if "lastLogonTimestamp" in user.keys():
                user["lastLogonTimestamp"] = _get_last_logon(user["lastLogonTimestamp"])
            if "lockoutTime" in user.keys():
                user["lockoutTime"] = convert_ad_timestamp(user["lockoutTime"], json_safe=json_safe)
            if "pwdLastSet" in user.keys():
                user["pwdLastSet"] = convert_ad_timestamp(user["pwdLastSet"], json_safe=json_safe)
            if "userAccountControl" in user.keys():
                user["userAccountControl"] = int(user["userAccountControl"])
                user["disabled"] = user["userAccountControl"] & 2 != 0
                user["passwordExpired"] = user["userAccountControl"] & 8388608 != 0
                user["passwordNeverExpires"] = user["userAccountControl"] & 65536 != 0
                user["smartcardRequired"] = user["userAccountControl"] & 262144 != 0

        finally:
            connection.unbind()

        return user

    def authenticate_user(self, username, password, base=None, attributes=None, json_safe=False):
        """
        Test if the given credentials are valid

        Args:
            username: The username
            password: The password
            base: Optionally overrides the base object DN
            attributes: A list of user attributes to return
            json_safe: Convert binary data to base64 and datetimes to human-readable strings

        Returns:
            A dictionary of user attributes is successful, or false if ir failed

        Raises:
            ldap.LDAP_ERROR
        """
        credentials = dict(username=username, password=password)
        try:
            user = self.get_user(username,
                                 credentials=credentials,
                                 base=base,
                                 attributes=attributes,
                                 json_safe=json_safe)
            return user
        except ldap.INVALID_CREDENTIALS:
            return False

    def get_group(self, group_string, base=None, credentials=None, attributes=None, json_safe=False):
        """
        Searches for a unique group object and returns its attributes

        Args:
            group_string: A group name, cn, or dn
            base: Optionally override the base object dn
            credentials: A optional dictionary of the username and password to use.
            If credentials are not passed, the credentials from the initial EasyAD configuration are used.
            attributes: An optional list of attributes to return. Otherwise uses self.group_attributes.
            To return all attributes, pass an empty list.
            json_safe: If true, convert binary data to base64 and datetimes to human-readable strings

        Returns:
            A dictionary of group attributes

        Raises:
            ValueError: Query returned no or multiple results
            ldap.LDAP_ERROR: An LDAP error occurred
        """
        if base is None:
            base = self.config["AD_BASE_DN"]

        if attributes is None:
            attributes = self.group_attributes

        group_filter = "(&(objectClass=Group)(|(cn={0})(distinguishedName={0})))".format(
            escape_filter_chars(group_string))

        connection = ADConnection(self.config)
        try:
            connection.bind(credentials)
            results = connection.ad.search_s(base=base,
                                             scope=ldap.SCOPE_SUBTREE,
                                             filterstr=group_filter,
                                             attrlist=attributes)

            results = decode_ldap_results(results, json_safe=json_safe)

            if len(results) == 0:
                raise ValueError("No such group")
            elif len(results) > 1:
                raise ValueError("The query returned more than one result")

        finally:
            connection.unbind()

        group = results[0]
        if "member" in group.keys():
            group["member"] = sorted(group["member"], key=lambda dn: dn.lower())

        return group

    def resolve_user_dn(self, user, base=None, credentials=None, json_safe=False):
        """
        Returns a user's DN when given a principalAccountName, sAMAccountName, email, or DN

        Args:
            user: A principalAccountName, sAMAccountName, email, or DN
            base: Optionally overrides the base object DN
            credentials: An optional dictionary of the username and password to use
            json_safe: If true, convert binary data to base64 and datetimes to human-readable strings

        Returns:
            The user's DN

        Raises:
            ldap.LDAP_ERROR
        """
        if isinstance(user, dict):
            user = user["distinguishedName"]
        elif isinstance(user, str) or isinstance(user, unicode):
            if not user.lower().startswith("cn="):
                user = self.get_user(user, base=base, credentials=credentials, json_safe=json_safe)["distinguishedName"]
        else:
            raise ValueError("User passed as an unsupported data type")
        return user

    def resolve_group_dn(self, group, base=None, credentials=None, json_safe=False):
        """
        Returns a group's DN when given a principalAccountName, sAMAccountName, email, or DN

        Args:
            group: A group name, cn, or dn
            base: Optionally overrides the base object DN
            credentials: An optional dictionary of the username and password to use
            json_safe: If true, convert binary data to base64 and datetimes to human-readable strings

        Returns:
            The groups's DN

        Raises:
            ldap.LDAP_ERROR
        """
        if isinstance(group, dict):
            group = group["distinguishedName"]
        elif isinstance(group, str) or isinstance(group, unicode):
            if not group.lower().startswith("cn="):
                group = self.get_group(group, base=base, credentials=credentials, json_safe=json_safe)["distinguishedName"]
        else:
            raise ValueError("Group passed as an unsupported data type")
        return group

    def get_all_user_groups(self, user, base=None, credentials=None, json_safe=False):
        """
        Returns a list of all group DNs that a user is a member of, including nested groups

        Args:
            user: A username, distinguishedName, or a dictionary containing a distinguishedName
            base: Overrides the configured base object dn
            credentials: An optional dictionary of the username and password to use
            json_safe: If true, convert binary data to base64 and datetimes to human-readable strings

        Returns:
            A list of group DNs that the user is a member of, including nested groups

        Raises:
            ldap.LDAP_ERROR

        Notes:
            This call can be taxing on an AD server, especially when used frequently.
            If you just need to check if a user is a member of a group,
            use EasyAD.user_is_member_of_group(). It is *much* faster.
        """
        user_dn = self.resolve_user_dn(user)
        if base is None:
            base = self.config["AD_BASE_DN"]
        filter_string = "(member:1.2.840.113556.1.4.1941:={0})".format(escape_filter_chars(user_dn))
        connection = ADConnection(self.config)
        try:
            connection.bind(credentials)
            results = connection.ad.search_s(base,
                                             ldap.SCOPE_SUBTREE,
                                             filterstr=filter_string,
                                             attrlist=["distinguishedName"])

            return sorted(list(map(lambda x: x["distinguishedName"],
                                   decode_ldap_results(results, json_safe=json_safe))), key=lambda s: s.lower())
        finally:
            connection.unbind()

    def get_all_users_in_group(self, group, base=None, credentials=None, json_safe=False):
        """
        Returns a list of all user DNs that are members of a given group, including from nested groups

       Args:
           group: A group name, cn, or dn
           base: Overrides the configured base object dn
           credentials: An optional dictionary of the username and password to use
           json_safe: If true, convert binary data to base64 and datetimes to human-readable strings

       Returns:
           A list of all user DNs that are members of a given group, including users from nested groups

        Raises:
            ldap.LDAP_ERROR

       Notes:
           This call can be taxing on an AD server, especially when used frequently.
           If you just need to check if a user is a member of a group,
           use EasyAD.user_is_member_of_group(). It is *much* faster.
       """
        group = self.resolve_group_dn(group)
        if base is None:
            base = self.config["AD_BASE_DN"]
        filter_string = "(&(objectClass=user)(memberof:1.2.840.113556.1.4.1941:={0}))".format(
            escape_filter_chars(group))
        connection = ADConnection(self.config)
        try:
            connection.bind(credentials)
            results = connection.ad.search_s(base,
                                             ldap.SCOPE_SUBTREE,
                                             filterstr=filter_string,
                                             attrlist=["distinguishedName"])

            return sorted(list(map(lambda x: x["distinguishedName"],
                                   decode_ldap_results(results, json_safe=json_safe))), key=lambda s: s.lower())

        finally:
            connection.unbind()

    def user_is_member_of_group(self, user, group, base=None, credentials=None):
        """
        Tests if a given user is a member of the given group

        Args:
            user: A principalAccountName, sAMAccountName, email, or DN
            group: A group name, cn, or dn
            base: An optional dictionary of the username and password to use
            credentials: An optional dictionary of the username and password to use

        Raises:
            ldap.LDAP_ERROR

        Returns:
            A boolean that indicates if the given user is a member of the given group
        """
        user = self.resolve_user_dn(user, base=base, credentials=credentials)
        group = self.resolve_group_dn(group, base=base, credentials=credentials)
        return len(self.get_all_users_in_group(group, base=user, credentials=credentials)) > 0


