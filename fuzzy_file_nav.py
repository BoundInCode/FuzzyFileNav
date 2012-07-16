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
        if key == "pikachoose_window_showing":
            return FuzzyFileNavCommand.active == operand  
        if key == "at_pikachoose_start":
            return (FuzzyFileNavCommand.active and len(line_text) < 1) == operand

    def on_modified(self, view):
        if FuzzyFileNavCommand.active and FuzzyFileNavCommand.view_id and FuzzyFileNavCommand.view_id == view.id():
            sel = view.sel()[0]
            win = view.window()
            line_text = view.substr(view.line(sel))

            if len(FuzzyFileNavCommand.initial_text)>0 and len(line_text) < 1:
                FuzzyFileNavCommand.fuzzy_reload = True
                win.run_command("fuzzy_file_nav", {"start": FuzzyFileNavCommand.cwd})

            # Go Home
            m = re.match(r"^(?:(~)|(/)|(.*\:))", line_text)
            if m:
                if m.group(1):
                    FuzzyFileNavCommand.fuzzy_reload = True
                    win.run_command("fuzzy_file_nav", {"start": HOME})
                elif m.group(2):
                    FuzzyFileNavCommand.fuzzy_reload = True
                    win.run_command("fuzzy_file_nav", {"start": ROOT})
                elif m.group(3):
                    FuzzyFileNavCommand.fuzzy_reload = True
                    win.run_command("fuzzy_file_nav", {"start": FuzzyFileNavCommand.cwd, "initial_text":line_text})
                # elif m.group(3):
                #     win.run_command("hide_overlay")
                #     FuzzyFileNavCommand.reset()
                #     win.run_command("fuzzy_folder_create", {"cwd": FuzzyFileNavCommand.cwd})
                # elif m.group(4):
                #     win.run_command("hide_overlay")
                #     FuzzyFileNavCommand.reset()
                #     win.run_command("fuzzy_file_create", {"cwd": FuzzyFileNavCommand.cwd})

            if view.substr(sel.a-1) == '/':
                FuzzyFileNavCommand.fuzzy_reload = True
                start = path.join(FuzzyFileNavCommand.cwd, line_text)
                win.run_command("fuzzy_file_nav", {"start": start})


class FuzzyFileCreateCommand(sublime_plugin.WindowCommand):
    def run(self, cwd):
        self.cwd = cwd
        self.window.show_input_panel(
            "Create File:",
            "",
            self.make,
            None,
            None
        )

    def make(self, value):
        name = path.join(self.cwd, value)
        if path.exists(self.cwd) and not path.exists(name):
            try:
                with open(name, "a"):
                    pass
                self.window.open_file(name)
            except:
                sublime.error_message("Could not create %d!" % name)


class FuzzyFolderCreateCommand(sublime_plugin.WindowCommand):
    def run(self, cwd):
        self.cwd = cwd
        self.window.show_input_panel(
            "Make Directory:",
            "",
            self.make,
            None,
            None
        )

    def make(self, value):
        name = path.join(self.cwd, value)
        if path.exists(self.cwd) and not path.exists(name):
            try:
                os.makedirs(name)
            except:
                sublime.error_message("Could not create %d!" % name)


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
        FuzzyFileNavCommand.files = self.get_files(cwd)
        if FuzzyFileNavCommand.initial_text[-1:] == ':':
            FuzzyFileNavCommand.files.extend(
                ["Create File "+FuzzyFileNavCommand.initial_text,
                "Create New Folder "+FuzzyFileNavCommand.initial_text+"/"])
        self.window.show_quick_panel(FuzzyFileNavCommand.files, self.check_selection)

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

    def create_file(self,path):
        print 'creating file'
        name = path.join(FuzzyFileNavCommand.cwd, FuzzyFileNavCommand.initial_text[:-1])
        if path.exists(FuzzyFileNavCommand.cwd) and not path.exists(name):
            try:
                with open(name, "a"):
                    pass
                self.window.open_file(name)
            except:
                sublime.error_message("Could not create %d!" % name)

    def create_folder(self,path):
        print 'creating folder'
        name = path.join(FuzzyFileNavCommand.cwd, FuzzyFileNavCommand.initial_text[:-1])
        if path.exists(FuzzyFileNavCommand.cwd) and not path.exists(name):
            try:
                os.makedirs(name)
            except:
                sublime.error_message("Could not create %d!" % name)

    def check_selection(self, selection):
        if selection > -1:
            FuzzyFileNavCommand.fuzzy_reload = False
            # The first selection is the "go up a directory" option.
            FuzzyFileNavCommand.cwd = self.back_dir(FuzzyFileNavCommand.cwd) if selection == 0 else path.join(FuzzyFileNavCommand.cwd, FuzzyFileNavCommand.files[selection])
            if FuzzyFileNavCommand.initial_text[:-1] == ':':
                if selection == len(FuzzyFileNavCommand.files-1):
                    self.create_file()
                elif selection == len(FuzzyFileNavCommand.files-2):
                    self.create_folder()

            # Check if the option is a folder or if we are at the root (needed for windows)
            if (path.isdir(FuzzyFileNavCommand.cwd) or FuzzyFileNavCommand.cwd == self.get_root_path()):
                try:
                    self.display_files(FuzzyFileNavCommand.cwd)
                except:
                    # Inaccessible folder try backing up
                    sublime.error_message(FuzzyFileNavCommand.cwd + "is not accessible!")
                    FuzzyFileNavCommand.cwd = self.back_dir(FuzzyFileNavCommand.cwd)
                    self.display_files(FuzzyFileNavCommand.cwd)
            else:
                try:
                    self.window.open_file(FuzzyFileNavCommand.cwd)
                    FuzzyFileNavCommand.reset()
                except:
                    FuzzyFileNavCommand.reset()
                    sublime.error_message(FuzzyFileNavCommand.cwd + "is not accessible!")
        elif not FuzzyFileNavCommand.fuzzy_reload:
            FuzzyFileNavCommand.reset()
        else:
            FuzzyFileNavCommand.fuzzy_reload = False
