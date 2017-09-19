from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.properties import StringProperty
from mopopup import MOPopup
from character_select import CharacterSelect

import re

from irc_mo import IrcConnection, ConnectionManger
from user import User, CurrentUserHandler

SERVER = "chat.freenode.net"
PORT = 6665
CHANNEL = "##mysteryonlinetest"


class LoginScreen(Screen):
    username = StringProperty('')

    def __init__(self, **kwargs):
        super(LoginScreen, self).__init__(**kwargs)
        self.picked_char = None

    def on_login_clicked(self, *args):
            self.validate_username()
            self.set_username_as_last_used()
            self.set_current_user()
            self.create_irc_connection()

    def validate_username(self):
        if not self.is_username_valid():
            popup = MOPopup("Error", "Invalid username", "Whatever you say, mate")
            popup.open()

    def create_irc_connection(self):
        user_handler = App.get_running_app().get_user_handler()
        connection = IrcConnection(SERVER, PORT, CHANNEL, self.username)
        user_handler.set_connection_manager(ConnectionManger(connection))
        self.manager.irc_connection = connection

    def set_current_user(self):
        user = User(self.username)
        user_handler = CurrentUserHandler(user)
        if self.picked_char is not None:
            user.set_char(self.picked_char)
            user.get_char().load()
        App.get_running_app().set_user(user)
        App.get_running_app().set_user_handler(user_handler)

    def set_username_as_last_used(self):
        config = App.get_running_app().config
        config.set('other', 'last_username', self.username)

    # noinspection PyTypeChecker
    def is_username_valid(self):
        p = re.compile(r"[a-z_\d][a-z_\d-]+", re.I)
        if not re.fullmatch(p, self.username):
            return False
        return True

    def on_select_clicked(self, *args):
        cs = CharacterSelect()
        cs.bind(on_dismiss=self.on_picked)
        cs.open()

    def on_picked(self, inst):
        self.picked_char = inst.picked_char
