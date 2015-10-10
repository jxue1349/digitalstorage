#!/usr/bin/env python
#
# Copyright 2015 WhereLast Inc.
#
###
################# user web page handler ########################
###
from library import *
from login import LoginHandler


class SettingHandler(LoginHandler):
	def render_front(self, email="", objectPlace="", img_url=None):
		self.render("setting.html", email=email, objectPlace=objectPlace, img_url=img_url)

	def get(self):
		if self.user:
			self.render_front(email=self.user.userEmail)
		else:
			self.redirect('/login')
	
	def post(self):
		self.render_front(email=self.user.userEmail)


