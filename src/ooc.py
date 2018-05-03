import threading
from datetime import datetime

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.properties import ObjectProperty
from kivy.uix.label import Label
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.utils import escape_markup
from kivy.logger import Logger

from private_message_screen import PrivateMessageScreen
from user_box import UserBox

import time
import youtube_dl
import os

ytdl_format_options = {
    'format': 'mp3/best',#was "bestaudio/best" but apperantly YT discriminates against certain extentions
    'outtmpl': 'temp.mp3',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}
YDlist = ['youtube', 'vimeo'] #dailymotion's files are way too big and TAKE SO LONG TO DOWNLOAD, but it's in this devbuild
#dictonary that dictates what the downloader has to do

class OOCLogLabel(Label):
    def __init__(self, **kwargs):
        super(OOCLogLabel, self).__init__(**kwargs)


class MusicTab(TabbedPanelItem):
    url_input = ObjectProperty(None)
    loop_checkbox = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(MusicTab, self).__init__(**kwargs)
        self.track = None
        self.loop = True
        self.is_loading_music = False

    def on_music_play(self, url=None):
        if self.is_loading_music:
            return
        self.is_loading_music = True
        if url is None:
            url = self.url_input.text

        def checker(self, send_to_all=True):
            #Start off by checking whether yt can 1) download it 2) the extractor type 3) length
            #The meta data is usefull cause with it we could avoid stopping tracks to swap with "fake songs", ex. link to stackoverflow
            #This also means that file can be checked ahead of time before downloading until we get streaming down
            #Most of music play has been moved to another thread for this, this has the downside that sending music can take some time
            #What still needs to be done is removing the "fake song" url from the input box
            #After feedback from master Zack, this could be later implemented in the refactoring build, with massive amounts of tweaking mind you
            #However, despite the fact that i made i format list way back in this code, i still fear that playlists and channels may cause issues
            #Further experimentation is required
            try:
                Tstart = time.time()
                with youtube_dl.YoutubeDL(ytdl_format_options) as ydl:
                    VideoDictionary = ydl.extract_info(
                        url,
                        download=False
                    )
                Tend = time.time()
                print('Meta download took: ' + str(Tend - Tstart))#Either my laptop is slow af or this download takes more than a second
                if VideoDictionary['extractor'] == 'Dropbox':
                    pass
                elif any(VideoDictionary['extractor'] in website for website in YDlist) and VideoDictionary[
                    'duration'] < 1800:#length checking and if the website is in the format list
                    pass
                else:
                    Logger.warning('Music: not in the whitelist of websites or is too long')
                    App.get_running_app().get_main_screen().log_window.add_entry("Music: not in the whitelist of websites or is too long.\n")
                    self.is_loading_music = False
                    send_to_all = False
                    return send_to_all
            except:
                Logger.warning('Music: url not supported by youtube-dl')
                App.get_running_app().get_main_screen().log_window.add_entry("URL not supported by youtube-dl.\n")
                self.is_loading_music = False
                send_to_all = False
                return send_to_all

            if send_to_all:
                #print("SEND TO ALL = TRUE")
                self.url_input.text = ""
                connection_manager = App.get_running_app().get_user_handler().get_connection_manager()
                connection_manager.update_music(url)
                main_screen = App.get_running_app().get_main_screen()
                main_screen.log_window.add_entry("You changed the music.\n")

            def play_song(root):
                track = root.track
                if track is not None and track.state == 'play':
                    track.stop()
                try:
                    os.remove("temp.mp3")  # the downloader doesn't overwrite files with the same name
                except FileNotFoundError:
                    print("No temp in directory.")  # if the first thing they play when joining MO is a yt link
                with youtube_dl.YoutubeDL(ytdl_format_options) as ydl:  # the actual downloading
                    Tstart = time.time()
                    ydl.download([url])
                    Tend = time.time()
                    print('MP3 download took: ' + str(Tend - Tstart))
                track = SoundLoader.load("temp.mp3")
                config_ = App.get_running_app().config
                track.volume = config_.getdefaultint('sound', 'music_volume', 100) / 100
                track.loop = root.loop
                track.play()
                root.track = track
                root.is_loading_music = False
            play_song(self)

        threading.Thread(target=checker, args=(self,)).start()
        #It just works

    def music_stop(self, local=True):
        if self.track is not None:
            if self.track.state == 'play':
                self.track.stop()
                main_screen = App.get_running_app().get_main_screen()
                if local:
                    connection = App.get_running_app().get_user_handler().get_connection_manager()
                    connection.update_music("stop")
                    main_screen.log_window.add_entry("You stopped the music.\n")

    def on_loop(self, value):
        self.loop = value

    def reset_music(self, *args):
        self.is_loading_music = False
        if self.track is not None:
            self.track.stop()


class OOCWindow(TabbedPanel):
    user_list = ObjectProperty(None)
    ooc_chat_header = ObjectProperty(None)
    ooc_input = ObjectProperty(None)
    blip_slider = ObjectProperty(None)
    music_slider = ObjectProperty(None)
    music_tab = ObjectProperty(None)
    effect_slider = ObjectProperty(None)
    chat_grid = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(OOCWindow, self).__init__(**kwargs)
        self.online_users = {}
        self.ooc_notif = SoundLoader.load('sounds/general/notification.mp3')
        self.pm_notif = SoundLoader.load('sounds/general/codeccall.wav')
        self.pm_open_sound = SoundLoader.load('sounds/general/codecopen.wav')
        self.ooc_play = True
        self.chat = PrivateMessageScreen()
        self.muted_users = []
        self.pm_buttons = []
        self.ooc_chat = OOCLogLabel()
        self.counter = 0

    def ready(self, main_scr):
        self.ooc_chat.bind(on_ref_press=main_scr.log_window.copy_text)
        self.add_user(main_scr.user)
        self.chat_grid.bind(minimum_height=self.chat_grid.setter('height'))
        self.ooc_chat.bind(on_ref_press=main_scr.log_window.copy_text)
        self.chat_grid.add_widget(self.ooc_chat)
        config = App.get_running_app().config  # The main config
        config.add_callback(self.on_blip_volume_change, 'sound', 'blip_volume')
        self.blip_slider.value = config.getdefaultint('sound', 'blip_volume', 100)
        config.add_callback(self.on_music_volume_change, 'sound', 'music_volume')
        self.music_slider.value = config.getdefaultint('sound', 'music_volume', 100)
        config.add_callback(self.on_ooc_volume_change, 'sound', 'effect_volume')
        self.effect_slider.value = config.getdefaultint('sound', 'effect_volume', 100)
        self.ooc_chat_header.bind(on_press=self.on_ooc_checked)
        self.chat.ready()
        main_scr = App.get_running_app().get_main_screen()
        if self.chat.irc is None:
            self.chat.irc = main_scr.manager.irc_connection
        self.chat.username = main_scr.user.username
        Clock.schedule_interval(self.update_private_messages, 1.0 / 60.0)
        v = config.getdefaultint('sound', 'effect_volume', 100)
        self.ooc_notif.volume = v / 100
        self.pm_notif.volume = v / 100
        self.pm_open_sound.volume = v / 100

    def on_blip_volume_change(self, s, k, v):
        self.blip_slider.value = v

    def on_slider_blip_value(self, *args):
        config = App.get_running_app().config
        value = int(self.blip_slider.value)
        config.set('sound', 'blip_volume', value)

    def on_music_volume_change(self, s, k, v):
        self.music_slider.value = v

    def on_slider_music_value(self, *args):
        config = App.get_running_app().config
        value = int(self.music_slider.value)
        if self.music_tab.track is not None:
            self.music_tab.track.volume = value / 100
        config.set('sound', 'music_volume', value)

    def on_ooc_volume_change(self, s, k, v):
        self.effect_slider.value = v
        self.ooc_notif.volume = int(v) / 100
        self.pm_notif.volume = int(v) / 100
        self.pm_open_sound.volume = int(v) / 100

    def on_slider_effect_value(self, *args):
        config = App.get_running_app().config
        value = int(self.effect_slider.value)
        config.set('sound', 'effect_volume', value)

    def add_user(self, user):
        char = user.get_char()
        main_screen = App.get_running_app().get_main_screen()
        if char is None:
            char = ""
        else:
            char = char.name
        if user.username not in (main_screen.user.username, '@ChanServ', 'ChanServ'):
            user_box = UserBox(size_hint_y=None, height=40)
            user_box.lbl.text = "{}: {}\n".format(user.username, char)
            user_box.pm.id = user.username
            user_box.pm.bind(on_press=lambda x: self.open_private_msg_screen(user.username, user_box.pm))
            self.pm_buttons.append(user_box.pm)
            user_box.mute.bind(on_press=lambda x: self.mute_user(user, user_box.mute))
            self.user_list.add_widget(user_box)
            self.online_users[user.username] = user_box

    def update_char(self, username, char):
        user_box = self.online_users.get(username, None)
        if user_box is None:
            return
        user_box.set_char_label(char)

    def update_loc(self, username, loc):
        user_box = self.online_users.get(username, None)
        if user_box is None:
            return
        user_box.set_loc_label(loc)

    def update_subloc(self, username, subloc):
        user_box = self.online_users.get(username, None)
        if user_box is None:
            return
        user_box.set_sub_label(subloc)

    def open_private_msg_screen(self, username, pm):  # Opens the PM window
        self.chat.pm_window_open_flag = True
        pm.background_color = (1, 1, 1, 1)
        self.chat.build_conversation(username)
        self.chat.set_current_conversation_user(username)
        self.chat.open()
        self.pm_open_sound.play()

    def muted_sender(self, pm, muted_users):  # Checks whether the sender of a pm is muted
        for x in range(len(muted_users)):
            if pm.sender == muted_users[x].username:
                return True
        return False

    def update_private_messages(self, *args):  # Acts on arrival of PMs
        main_scr = App.get_running_app().get_main_screen()
        irc = main_scr.manager.irc_connection
        pm = irc.get_pm()
        if pm is not None:
            if pm.sender != self.chat.username:
                if not self.muted_sender(pm, self.muted_users):
                    if not self.chat.pm_window_open_flag:
                        for x in range(len(self.online_users)):
                            if pm.sender == self.pm_buttons[x].id:
                                self.pm_buttons[x].background_color = (1, 0, 0, 1)
                                break
                        if not self.chat.pm_flag and not self.chat.pm_window_open_flag:
                            self.pm_notif.play()
                    self.chat.pm_flag = True
                    self.chat.build_conversation(pm.sender)
                    self.chat.set_current_conversation_user(pm.sender)
                    self.chat.update_conversation(pm.sender, pm.msg)

    def mute_user(self, user, btn):
        if user in self.muted_users:
            self.muted_users.remove(user)
            btn.text = 'Mute'
        else:
            self.muted_users.append(user)
            btn.text = 'Unmute'

    def delete_user(self, username):
        try:
            label = self.online_users[username]
        except KeyError:
            return
        self.user_list.remove_widget(label)
        del self.online_users[username]

    def on_ooc_checked(self, *args):
        self.ooc_chat_header.background_normal = 'atlas://data/images/defaulttheme/button'
        self.ooc_chat_header.background_color = [1, 1, 1, 1]

    def update_ooc(self, msg, sender):
        ref = msg
        if sender == 'default':
            sender = App.get_running_app().get_user().username
        if 'www.' in msg or 'http://' in msg or 'https://' in msg:
            msg = "[u]{}[/u]".format(msg)
        if self.counter == 100:
            self.counter = 0
            self.ooc_chat = OOCLogLabel()
            self.chat_grid.add_widget(self.ooc_chat)
            main_scr = App.get_running_app().get_main_screen()
            self.ooc_chat.bind(on_ref_press=main_scr.log_window.copy_text)
        self.ooc_chat.text += "{0}: [ref={2}]{1}[/ref]\n".format(sender, msg, escape_markup(ref))
        self.counter += 1
        config = App.get_running_app().config
        if config.getdefaultint('other', 'ooc_scrolling', 1):
            self.ooc_chat.parent.parent.scroll_y = 0
        now = datetime.now()
        cur_date = now.strftime("%d-%m-%Y")
        cur_time = now.strftime("%H:%M:%S")
        log_msg = "<{} {}> {}: {}\n".format(cur_time, cur_date, sender, msg)
        with open('ooc_log.txt', 'a', encoding='utf-8') as f:
            f.write(log_msg)
        if self.current_tab != self.ooc_chat_header:
            color = [0, 0.5, 1, 1]
            if self.ooc_chat_header.background_color != color:
                self.ooc_chat_header.background_normal = ''
                self.ooc_chat_header.background_color = color
            if self.ooc_play:
                self.ooc_notif.play()
                config = App.get_running_app().config
                delay = config.getdefaultint('other', 'ooc_notif_delay', 60)
                Clock.schedule_once(self.ooc_time_callback, delay)
                self.ooc_play = False

    def ooc_time_callback(self, *args):
        self.ooc_play = True

    def send_ooc(self):
        Clock.schedule_once(self.refocus_text)
        msg = self.ooc_input.text
        main_scr = App.get_running_app().get_main_screen()
        irc = main_scr.manager.irc_connection
        irc.send_special('OOC', msg)
        self.ooc_input.text = ""

    def refocus_text(self, *args):
        self.ooc_input.focus = True
