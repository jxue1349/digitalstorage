#!/usr/bin/env python
#
# Copyright 2015 WhereLast Inc.
#
###
################# user web page handler ########################
###
from library import *
from login import LoginHandler
from database import Ustorage
from database import UserGroup
import xml.dom.minidom
import re
from google.appengine.api import mail


invitation_body = """
					I've invited you to WhereLast.com!
					To accept this invitation, click the following link,
					or copy and paste the URL into your browser's address
					bar: 
						%s 
"""

class userHandler(LoginHandler):
	def render_front(self, email="", objectPlace="", img_url=None, user_groups=None, error=""):
		self.render("usern.html", email=email, objectPlace=objectPlace, img_url=img_url, user_groups=user_groups, error=error)

	def get(self):
		if self.user:
			user_groups = self.generate_user_groups()
			self.render_front(email=self.user.userEmail, user_groups=user_groups)
		else:
			self.redirect('/login')
	def get_coords(self, ip):
		url = "http://api.hostip.info/?ip=" + ip
		content = None
		try: 
			content = urllib2.urlopen(url).read()
		except urllib2.URLError:
			return

		if content:
			d = xml.dom.minidom.parseString(content)
			coords = d.getElementsByTagName("gml:coordinates")
			if coords and coords[0].childNodes[0].nodeValue:
				lon, lat = coords[0].childNodes[0].nodeValue.split(',')
				return db.GeoPt(lat, lon)

	def get_address(self, lat, lon):
		url = "https://maps.googleapis.com/maps/api/geocode/xml?latlng=%s,%s" % (lat, lon)
		content = None
		try:
			content = urllib2.urlopen(url).read()
		except urllib2.URLError:
			return
		if content:
			d = xml.dom.minidom.parseString(content)
			addrs = d.getElementsByTagName("formatted_address")
			if addrs and addrs[0].childNodes[0].nodeValue:
				return addrs[0].childNodes[0].nodeValue

	def loosematch(self, objectName):
		# do the auto correction from autocorrect lib -- this is slow
		# objectName = spell(objectName)

		# remove all the empty spaces from the beginning and end of the string
		objectNameStrip = objectName.strip(' ')
		# store the lower case
		objectNameLower = objectNameStrip.lower()
		return objectNameLower

	def inputstudy(self, userstore):
		isQuery = re.search('where|Where', userstore)
		userlist = userstore.split()
		objectName = ''
		objectLocation = ''
		if isQuery:
			Preposition = re.search(r"my", userstore)
			if Preposition:
				objectName = userstore[Preposition.end():]
			else:
				objectName = userlist[len(userlist)-1]
		elif userlist:
			Preposition = re.search(r" on | under | in | between ", userstore)
			if Preposition:
				objectName = userstore[:Preposition.start()]
				objectLocation = userstore[Preposition.end():]
		return (isQuery, objectName, objectLocation)

	def generate_invite_link(self, groupID):
		invitation_url = "http://www.wherelast.com/invite/code=%s" % (groupID)
		return invitation_url

	def generate_user_groups(self):
		groups = UserGroup.by_name(self.user.userEmail)
		user_groups = dict()
		for key in groups:
			user_group_name = re.search(r"(\d+)", key)
			if user_group_name:
				user_groups[key[user_group_name.end():]] = groups[key]
		if user_groups:
			return user_groups

	def get_object_groupid(self, groupName):
		groups = UserGroup.by_name(self.user.userEmail)
		for group in groups:
			object_groupID = re.search(groupName, group)
			if object_groupID:
				return group


	def post(self):
		ustore = self.request.get("userSubmit")
		userInput = self.request.get("userInput")
		isQuery = False
		objectName = ''
		objectLocation = ''
		if userInput:
			# get input from voice log
			isQuery, objectName, objectLocation = self.inputstudy(userInput)
			# handle the object name in a smart way
			objectName = self.loosematch(objectName)
		user_groups = self.generate_user_groups()
		group_name = self.request.get("group_name")
		to_addr = self.request.get("friend_email")
		group_invitation = self.request.get("invitation")
		user_type = "Private" # as default
		user_type = self.request.get("user_type")
		user_select_group = self.request.get("user_select_groups")
		user_list_group = self.request.get("user_select_group")
		print user_list_group

		if objectName and objectLocation:
			# store the data in the data base associate with user id
			# get the location from ip address
			objectGroupID = ''
			if user_type == 'Group':
				objectGroupID = self.get_object_groupid(user_select_group)
			user_store = Ustorage.store(userId=self.user.key().id(), objectName=objectName, objectLocation=objectLocation,
				objectType=user_type, objectGroupID=objectGroupID,
				objectGeoLocation=self.get_coords(self.request.remote_addr))
			user_store.put()
			self.render_front(email=self.user.userEmail, user_groups=user_groups)
		elif isQuery and objectName:
			# get from memcache first
			objectGroupID = self.get_object_groupid(user_select_group)
			userQuery = Ustorage.by_name_g(uid=self.user.key().id(), name=objectName, type=user_type, gid=objectGroupID)				
			img_url = None
			address = ""
			if userQuery is None:
				self.render_front(email=self.user.userEmail, objectPlace="didn't find any of matching items", user_groups=user_groups)
			else: 			
				(u_location, u_geolocation) = userQuery
				if u_geolocation != None:
					img_url = "http://maps.googleapis.com/maps/api/staticmap?size=380x300&sensor=false&" + 'markers=%s,%s' % (userQuery.objectGeoLocation.lat, userQuery.objectGeoLocation.lon)
					address = "in address: " + self.get_address(u_geolocation.lat, u_geolocation.lon)


				self.render_front(email=self.user.userEmail, 
						objectPlace="your %s is in/on %s %s"%(objectName, u_location, address), img_url=img_url, user_groups=user_groups)
		elif to_addr and group_invitation:
			if not valid_email(to_addr):
				self.render_front(email=self.user.userEmail, user_groups=user_groups, error="Not valid email")
			else:
				groupID = str(self.user.key().id()) + group_name				
				group_store = UserGroup.add_group(groupID=groupID, userEmail=self.user.userEmail, guestEmail=self.user.userEmail, userConfirmed="yes")
				group_store_friend = UserGroup.add_group(groupID=groupID, userEmail=self.user.userEmail, guestEmail=to_addr, userConfirmed="no")
				if group_store:
					group_store.put()
				if group_store_friend:
					user_groups = self.generate_user_groups()
					group_store_friend.put()
					message_sender = self.user.userEmail
					message_subject = "Inviation for WhereLast from %s" % message_sender
					message_body = invitation_body % (self.generate_invite_link(groupID))
					mail.send_mail(message_sender, to_addr, message_subject, message_body)
				else:
					error = "Already add %s into group %s" % (to_addr, group_name)
				self.render_front(email=self.user.userEmail, user_groups=user_groups, error=error)  
		else:
			self.render_front(email=self.user.userEmail, user_groups=user_groups)


