"""
Fuzzy File Navigation

Copyright (c) 2012 Isaac Muse <isaacmuse@gmail.com>
"""

import sublime
import sublime_plugin
import os
import os.path as path
import re

PLATFORM = sublime.platform()
ROOT = "/"
HOME = "/Users/liam"
REGEX_EXCLUDE = ["\\.[\\w]+"]

class FuzzyEventListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        # New window gained activation? Reset fuzzy command state
        if FuzzyFileNavCommand.active and view.window() and view.window().id() != FuzzyFileNavCommand.win_id:
            FuzzyFileNavCommand.reset()
        if FuzzyFileNavCommand.active and view.settings().get('is_widget'):
            if FuzzyFileNavCommand.view_id != view.id():
                FuzzyFileNavCommand.view_id = view.id()
            if not view.sel()[0].a: # compensating for on_activated being called 3 times...
                edit = view.begin_edit()
                view.insert(edit, 0, FuzzyFileNavCommand.initial_text)
                view.end_edit(edit)

    def on_query_context(self, view, key, operator, operand, match_all):
        sel = view.sel()[0]  
        line_text = view.substr(view.line(sel))
        if key == "fuzzy_window_showing":
            return FuzzyFileNavCommand.active == operand  
        if key == "at_fuzzy_start":
            return (FuzzyFileNavCommand.active and len(line_text) < 1) == operand

    def on_modified(self, view):
        if FuzzyFileNavCommand.active and FuzzyFileNavCommand.view_id and FuzzyFileNavCommand.view_id == view.id():
            sel = view.sel()[0]
            win = view.window()
            line_text = view.substr(view.line(sel))
            if line_text != FuzzyFileNavCommand.initial_text:
                view.run_command('fuzzy_reload')
            return

            if len(FuzzyFileNavCommand.initial_text)>0 and len(line_text) < 1:
                FuzzyFileNavCommand.fuzzy_reload = True
                win.run_command("fuzzy_file_nav", {"start": FuzzyFileNavCommand.cwd})

            # Go Home
            m = re.match(r"^(?:(~/)|(/))", line_text)
            if m:
                if m.group(1):
                    FuzzyFileNavCommand.fuzzy_reload = True
                    win.run_command("fuzzy_file_nav", {"start": HOME})
                elif m.group(2):
                    FuzzyFileNavCommand.fuzzy_reload = True
                    win.run_command("fuzzy_file_nav", {"start": ROOT})

            # fast select folder
            if view.substr(sel.a-1) == '/':
                FuzzyFileNavCommand.fuzzy_reload = True
                start = path.join(FuzzyFileNavCommand.cwd, line_text)
                win.run_command("fuzzy_file_nav", {"start": start})

class FuzzyReloadCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        FuzzyFileNavCommand.fuzzy_reload = True
        sel = view.sel()[0]  
        line_text = view.substr(view.line(sel))
        self.view.window().run_command("fuzzy_file_nav", {"start": FuzzyFileNavCommand.cwd, "initial_text":line_text})

class FuzzyShowHiddenCommand(sublime_plugin.WindowCommand):
    def run(self):
        start = FuzzyFileNavCommand.cwd
        FuzzyFileNavCommand.fuzzy_reload = True
        self.window.run_command("fuzzy_file_nav", {"start": start, "regex_exclude": False,"initial_text":"."})

class FuzzyStartFromFileCommand(sublime_plugin.TextCommand):
    def run(self, edit, regex_exclude=True):
        # Check if you can retrieve a file name (means it exists on disk).
        name = self.view.file_name()
        if name:
            self.view.window().run_command("fuzzy_file_nav", {"start": path.dirname(name), "regex_exclude": regex_exclude})


class FuzzyFileNavCommand(sublime_plugin.WindowCommand):
    active = False
    win_id = None
    view_id = None
    regex_exclude = []
    fuzzy_reload = False

    @classmethod
    def reset(cls):
        cls.active = False
        cls.win_id = None
        cls.view_id = None

    def run(self, start=None, regex_exclude=True, initial_text=""):
        if FuzzyFileNavCommand.active:
            self.window.run_command("hide_overlay")

        FuzzyFileNavCommand.active = True
        FuzzyFileNavCommand.view_id = None
        FuzzyFileNavCommand.initial_text = initial_text
        FuzzyFileNavCommand.win_id = self.window.id()
        FuzzyFileNavCommand.regex_exclude = REGEX_EXCLUDE if regex_exclude else []

        # Check if a start destination has been given
        # and ensure it is valid.
        FuzzyFileNavCommand.cwd = self.get_root_path() if start == None or not path.exists(start) or not path.isdir(start) else unicode(start)

        # Get and display options.
        try:
            self.display_files(FuzzyFileNavCommand.cwd)
        except:
            FuzzyFileNavCommand.reset()
            sublime.error_message(FuzzyFileNavCommand.cwd + " is not accessible!")

    def get_files(self, cwd):
        # Get files/drives (windows).
        files = self.get_drives() if PLATFORM == "windows" and cwd == u"" else os.listdir(cwd)
        folders = []
        documents = []
        for f in files:
            valid = True
            full_path = path.join(cwd, f)

            # Check exclusion regex to omit files.
            if valid:
                for regex in FuzzyFileNavCommand.regex_exclude:
                    if re.match(regex, f):
                        valid = False

            # Store file/folder info.
            if valid:
                if not path.isdir(full_path):
                    documents.append(f)
                else:
                    folders.append(f + ("\\" if PLATFORM == "windows" else "/"))
        return [u".."] + sorted(folders) + sorted(documents)

    def get_root_path(self):
        # Windows doesn't have a root, so just
        # return an empty string to represent its root.
        return u"" if PLATFORM == "windows" else u"/"

    def display_files(self, cwd):
        f = FuzzyFileNavCommand
        f.files = self.get_files(cwd)

        if len(f.initial_text)>0 and not path.exists(path.join(cwd,f.initial_text)):
            f.files.extend(
                ["Create File "+f.initial_text,"Create New Folder "+f.initial_text+"/"])
        self.window.show_quick_panel(f.files, self.check_selection)

    def back_dir(self, cwd):
        prev = path.dirname(path.dirname(cwd))

        # On windows, if you try and get the
        # dirname of a drive, you get the drive.
        # So if the previous directory is the same
        # as the current, back out of the drive and
        # list all drives.
        return self.get_root_path() if prev == cwd else prev

    def get_drives(self):
        # Search through valid drive names and see if they exist.
        return [unicode(d + ":") for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if path.exists(d + ":")]

    def create_file(self):
        print 'creating file'
        name = path.join(FuzzyFileNavCommand.cwd, FuzzyFileNavCommand.initial_text)
        if path.exists(FuzzyFileNavCommand.cwd) and not path.exists(name):
            try:
                with open(name, "a"):
                    pass
                self.window.open_file(name)
            except:
                sublime.error_message("Could not create %d!" % name)

    def create_folder(self):
        print 'creating folder'
        name = path.join(FuzzyFileNavCommand.cwd, FuzzyFileNavCommand.initial_text)

        if path.exists(FuzzyFileNavCommand.cwd) and not path.exists(name):
            try:
                os.makedirs(name)
            except:
                sublime.error_message("Could not create %d!" % name)

    def check_selection(self, selection):
        f = FuzzyFileNavCommand
        if selection > -1:
            f.fuzzy_reload = False
            # The first selection is the "go up a directory" option.
            if f.initial_text:
                if selection == len(f.files)-2:
                    self.create_file()
                elif selection == len(f.files)-1:
                    self.create_folder()
                return
            f.cwd = self.back_dir(f.cwd) if selection == 0 else path.join(f.cwd, f.files[selection])

            # Check if the option is a folder or if we are at the root (needed for windows)
            if (path.isdir(f.cwd) or f.cwd == self.get_root_path()):
                try:
                    self.display_files(f.cwd)
                except:
                    # Inaccessible folder try backing up
                    sublime.error_message(f.cwd + "is not accessible!")
                    f.cwd = self.back_dir(f.cwd)
                    self.display_files(f.cwd)
            else:
                try:
                    self.window.open_file(f.cwd)
                    f.reset()
                except:
                    f.reset()
                    sublime.error_message(f.cwd + "is not accessible!")
        elif not f.fuzzy_reload:
            f.reset()
        else:
            f.fuzzy_reload = False
