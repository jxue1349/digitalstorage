#!/usr/bin/env python
#
# Copyright 2015 WhereLast Inc.
#
###########  Database  ################
#######################################
import re
from library import *
from google.appengine.ext import db
from google.appengine.api import memcache

def users_key(group = 'default'):
	return db.Key.from_path('users', group)

# user data base
class User(db.Model):
	userEmail = db.StringProperty(required = True)
	userPassword = db.StringProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)
	@classmethod
	def by_id(cls, uid):
		return cls.get_by_id(uid, parent = users_key())

	@classmethod
	def by_name(cls, name):
		u = cls.all().filter('userEmail =', name).get()
		return u

	@classmethod
	def register(cls, name, pw, email = None):
		pw_hash = make_pw_hash(name, pw)
		return cls(parent = users_key(),
			userEmail = name, userPassword = pw_hash)

	@classmethod
	def login(cls, name, pw):
		u = cls.by_name(name)
		if u and valid_pw(name, pw, u.userPassword):
			return u
		elif not u:
			return 1

# user group database definition
class UserGroup(db.Model):
	"""docstring for UserGroup"""
	userEmail = db.StringProperty(required = True)
	userGroupID = db.StringProperty(required = True)
	userConfirmed = db.StringProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)
	last_modified = db.DateTimeProperty(auto_now = True)

	def render(self):
		self._render_text = self.userEmail.replace('\n', '<br>')
		return self.userGroupID

	@classmethod
	def by_id(cls, groupID):
		cache_result = memcache.get(groupID)
		if cache_result is None:
			results = cls.all().filter('userGroupID = ', groupID).order('-last_modified')
			cache_result = []
			if results:
				for result in results:
					cache_result.append(result.userEmail)
				memcache.add(key=groupID, value=cache_result)
		return cache_result

	@classmethod
	def by_name(cls, userEmail):
		results = memcache.get(userEmail)
		if results is None:
			userQueries = cls.all().filter('userEmail = ', userEmail).order('-created')
			if userQueries is not None:
				results = dict()
				for userQuery in userQueries:
					userlist = cls.by_id(userQuery.userGroupID)
					results[userQuery.userGroupID] = userlist
				memcache.add(key=userEmail, value=results)
		#result = memcache.get(userEmail)
		#if result is None:
		#results = cls.all().filter('userEmail = ', userEmail).order('-created')
		#if results is not None:
		return results

	@classmethod
	def by_group_name(cls, groupID, userEmail):
		o = cls.all().filter('userGroupID = ', groupID).filter('userEmail = ', userEmail).get()
		return o

	@classmethod
	def add_group(cls, groupID, userEmail, guestEmail, userConfirmed):
		objectG = cls.by_group_name(groupID, guestEmail)
		if objectG:
			if userConfirmed:
				objectG.userConfirmed = userConfirmed
		else:
			# update memcache if it has already log the user lists of the group lists
			userlist = cls.by_id(groupID)
			if userlist:
				if guestEmail not in userlist:
					userlist.append(guestEmail)
					memcache.set(key=groupID, value=userlist)
					user_tree = memcache.get(userEmail)
					if user_tree:
						for group_id in user_tree:
							if group_id == groupID:
								user_tree[groupID] = userlist
								memcache.set(key=userEmail, value=user_tree)
			return cls(userEmail=guestEmail, userGroupID=groupID, userConfirmed=userConfirmed)

# TO-DO-LIST: 1. send object id linke to user group to find out instead of object name
# 2. fudgeable object
# 3. location history: updater + location + update time
class Ustorage(db.Model):
	#uid, object-name, object-location, geolocation, created
	userId = db.IntegerProperty(required = True)
	#GroupId = db.StringProperty(required = True)
	objectName = db.StringProperty(required = True)
	objectLocation = db.StringProperty(required = True)
	objectType = db.StringProperty(required = True)
	objectGroupID = db.StringProperty()
	objectGeoLocation = db.GeoPtProperty()
	created = db.DateTimeProperty(auto_now_add = True)

	@classmethod
	def by_name_cache(cls, uid, name):
		key = repr(uid) + name
		result = memcache.get(key)
		if result is None:
			userQuery = Ustorage.by_name(uid=uid, name=name)
			if userQuery is not None:
				result = (userQuery.objectLocation, userQuery.objectGeoLocation)
				memcache.set(key=key, value=result)
		return result

	@classmethod
	def by_name_g(cls, uid, name, type, gid):
		# 1. search uid + name
		# 2. if didn't find any, check type == group
		# 3. if type = group, and gid is valid, get the group owner uid
		# 4. check uid + name + type == group
		userQuery = Ustorage.by_name(uid=uid, name=name)
		if userQuery is not None:
			result = (userQuery.objectLocation, userQuery.objectGeoLocation)
			return result
		elif type == 'Group' and gid:
			groupOwner_uid = re.search(r"(\d+)", gid)
			if groupOwner_uid:
				uid = gid[:groupOwner_uid.end()]
				#print uid + name
				userQuery = Ustorage.by_name_type(uid=int(uid), name=name, gid=gid)
				if userQuery:
					result = (userQuery.objectLocation, userQuery.objectGeoLocation)
					return result

	@classmethod
	def by_name_type(cls, uid, name, gid):
		allentries = cls.all()
		#for entry in allentries:
		#	print str(entry.userId) + entry.objectName
		o = allentries.filter('objectName =', name).filter('objectGroupID =', gid).get()
		#print o
		return o


	@classmethod
	def by_name(cls, uid, name):
		o = cls.all().filter('userId =', uid).filter('objectName =', name).get()
		return o

	@classmethod
	def store(cls, userId, objectName, objectLocation, objectType, objectGroupID = None, objectGeoLocation = None):
		objectT = cls.by_name(userId, objectName)
		key = repr(userId) + objectName
		if objectT and objectT.objectType == objectType:
			#already have the item, update the location
			# TO-DO-LIST: check the type before update the location
			objectT.objectLocation = objectLocation
			# update the memcache entry
			# memcache.set(key=key, value=(objectLocation, objectGeoLocation))
			return objectT
		else:
			#add to memcache
			# memcache.add(key=key, value=(objectLocation, objectGeoLocation))
			return cls(parent = users_key(),
				userId = userId, objectName = objectName, objectType = objectType, objectGroupID = objectGroupID,
				objectLocation = objectLocation, objectGeoLocation = objectGeoLocation)
	
