#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import jinja2
import webapp2
import re
import random
import string
import hashlib
import secret
import hmac
import urllib2
from google.appengine.ext import db
import xml.dom.minidom

template_dir = os.path.join(os.path.dirname(__file__), 'src')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                                autoescape = True)
# Render page handler 
class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))


class MainHandler(Handler):
    def get(self):
        self.render("index.html")

# Password hash function 
def make_salt():
	return "".join(random.choice(string.letters) for x in xrange(5))
def make_pw_hash(name, pw, salt=None):
	if not salt:
		salt = make_salt()
	h = hashlib.sha256(secret.secret() + name + pw + salt).hexdigest()
	return '%s|%s' % (h, salt)
def valid_pw(name, pw, h):
	salt = h.split("|")[1]
	return h == make_pw_hash(name, pw, salt)
def users_key(group = 'default'):
	return db.Key.from_path('users', group)
def make_secure_val(val):
	return '%s|%s' % (val, hmac.new(secret.secret(), val).hexdigest())
def check_secure_val(secure_val):
	val = secure_val.split('|')[0]
	if secure_val == make_secure_val(val):
		return val


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

# login/sign up page handler
class LoginHandler(Handler):
	def render_front(self, rtype="signin", useremail="", pwd="", cpwd="", error=""):
		self.render("login.html", rtype=rtype, useremail=useremail, pwd=pwd, cpwd=cpwd, error=error)

	def get(self):
		self.render_front();

	def set_secure_cookie(self, name, val):
		cookie_val = make_secure_val(val)
		self.response.headers.add_header(
			'Set-Cookie',
			'%s=%s; Path=/' % (name, cookie_val))

	def read_secure_cookie(self, name):
		cookie_val = self.request.cookies.get(name)
		return cookie_val and check_secure_val(cookie_val)

	def login(self, user):
		self.set_secure_cookie('user_id', str(user.key().id()))

	def logout(self):
		self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

	def initialize(self, *a, **kw):
		webapp2.RequestHandler.initialize(self, *a, **kw)
		uid = self.read_secure_cookie('user_id')
		self.user = uid and User.by_id(int(uid))

	def valid_email(self, email):
		email_re = re.compile(r"^[\S]+@[\S]+\.[\S]+$")
		return email and email_re.match(email)

	def valid_password(self, password):
		password_re = re.compile(r"^[a-zA-Z0-9_!@#$%^&*-]{3,20}$")
		return password and password_re.match(password)

	def post(self):
		signin = self.request.get("signin-button")
		signup = self.request.get("signup-button")
		email = self.request.get("email")
		pwd = self.request.get("pwd")

		error = ""
		if not self.valid_email(email):
			error = "invalid email address"
		if not self.valid_password(pwd):
			if signin:
				error = "invalid password"
			elif signup:
				error = "invalid password. Password should be 3-20 characters including numbers, letters and !@#$%^&*_"

		if signin: 
			if error:
				self.render_front(rtype="signin", useremail=email, pwd=pwd, error=error)
			else:
				# next step is to check user name and password is matching database
				# if yes, redirect to user.html
				# if not, re-render the login page with error message
				u = User.login(email, pwd)

				
				if u == 1:
					error = "account is not existing, try signup"
					self.render_front(rtype="signup", useremail=email, pwd=pwd, error=error)
				elif not u:
					error = "invalid password"
					self.render_front(rtype="signin", useremail=email, error=error)
				else:
					self.login(u)
					self.redirect('/user')

		elif signup:
			signup_confirm_pwd = self.request.get("conf-signup-pwd")

			if pwd != signup_confirm_pwd:
				error="Password doesn't match!"
			if error:
				self.render_front(rtype="signup", useremail=email, pwd=pwd, cpwd=signup_confirm_pwd, error=error)
			else:
				# check if the email is alrady registered
				# if yes, re-render the login page with error message
				# if no, add it to database, and then redirect to user.html
				u = User.by_name(email)
				if u:
					error = "%s is already registered" % (email)
					self.render_front(rtype="signin", useremail=email, pwd=pwd, cpwd=signup_confirm_pwd, error=error) 
				else:
					u = User.register(email, pwd)
					u.put()
					self.login(u)
					self.render('/user')
		else:
			self.render_front();
class Ustorage(db.Model):
	#uid, object-name, object-location, geolocation, created
	userId = db.IntegerProperty(required = True)
	#GroupId = db.StringProperty(required = True)
	objectName = db.StringProperty(required = True)
	objectLocation = db.StringProperty(required = True)
	objectGeoLocation = db.GeoPtProperty()
	created = db.DateTimeProperty(auto_now_add = True)

	@classmethod
	def by_name(cls, uid, name):
		o = cls.all().filter('userId =', uid).filter('objectName =', name).get()
		return o

	@classmethod
	def store(cls, userId, objectName, objectLocation, objectGeoLocation = None):
		objectT = cls.by_name(userId, objectName)
		if objectT:
			#already have the item, update the location
			objectT.objectLocation = objectLocation
			return objectT
		else:
			return cls(parent = users_key(),
				userId = userId, objectName = objectName, 
				objectLocation = objectLocation, objectGeoLocation = objectGeoLocation)
	

class userHandler(LoginHandler):
	def render_front(self, email="", objectPlace="", img_url=None):
		self.render("user.html", email=email, objectPlace=objectPlace, img_url=img_url)

	def get(self):
		if self.user:
			self.render_front(email=self.user.userEmail)
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



	def post(self):
		ustore = self.request.get("userSubmit")
		uquery = self.request.get("userQuery")
		objectName = self.request.get("userStuff")
		objectLocation = self.request.get("userPlace")
		objectNameFind = self.request.get("userFind")

		if ustore and objectName and objectLocation:
			# store the data in the data base associate with user id
			# get the location from ip address
			user_store = Ustorage.store(userId=self.user.key().id(), objectName=objectName, objectLocation=objectLocation,
				objectGeoLocation=self.get_coords(self.request.remote_addr))
			user_store.put()
			self.render_front(email=self.user.userEmail)
		elif uquery or (objectNameFind and ustore):
			userQuery = Ustorage.by_name(uid=self.user.key().id(), name=objectNameFind)
			img_url = None
			address = ""
			if not userQuery:
				self.render_front(email=self.user.userEmail, objectPlace="didn't find any of matching items")
			else: 
				if userQuery.objectGeoLocation != None:
					img_url = "http://maps.googleapis.com/maps/api/staticmap?size=380x300&sensor=false&" + 'markers=%s,%s' % (userQuery.objectGeoLocation.lat, userQuery.objectGeoLocation.lon)
					address = "in address: " + self.get_address(userQuery.objectGeoLocation.lat, userQuery.objectGeoLocation.lon)


				self.render_front(email=self.user.userEmail, 
						objectPlace="your %s is in/on %s %s"%(objectNameFind, userQuery.objectLocation, address), img_url=img_url)

		else: 
			self.render_front(email=self.user.userEmail)




class LogoutHandler(LoginHandler):
	def get(self):
		self.logout()
		self.redirect("/")	

app = webapp2.WSGIApplication([('/', MainHandler), 
							   ('/login', LoginHandler), 
							   ('/user', userHandler),
							   ('/logout', LogoutHandler)
							   ], debug=True)
