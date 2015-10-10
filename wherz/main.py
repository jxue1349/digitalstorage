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
import webapp2
# import different modules
import library
from login import LoginHandler
from login import LogoutHandler
from user import userHandler
from setting import SettingHandler

class MainHandler(library.Handler):
    def get(self):
        self.render("index.html")


app = webapp2.WSGIApplication([('/', MainHandler), 
							   ('/login', LoginHandler), 
							   ('/user', userHandler),
							   ('/logout', LogoutHandler),
							   ('/setting', SettingHandler)
							   ], debug=True)
