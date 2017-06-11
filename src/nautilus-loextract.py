#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of nautilus-loextract
#
# Copyright (C) 2017 Lorenzo Carbonell
# lorenzo.carbonell.cerezo@gmail.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#
import gi
try:
    gi.require_version('Gtk', '3.0')
    gi.require_version('GObject', '2.0')
    gi.require_version('GLib', '2.0')
    gi.require_version('Nautilus', '3.0')
except Exception as e:
    print(e)
    exit(-1)
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Nautilus as FileManager
from zipfile import ZipFile
import os
import shutil
from threading import Thread
import mimetypes
from urllib import unquote_plus

APP = '$APP$'
VERSION = '$VERSION$'

CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.config', APP.lower())
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)
CONFIG_FILE = os.path.join(CONFIG_DIR, '{0}.conf'.format(APP.lower()))

MARGIN = 10
MIMETYPES = ['application/vnd.oasis.opendocument.text',
             'application/vnd.oasis.opendocument.text-template',
             'application/vnd.oasis.opendocument.graphics',
             'application/vnd.oasis.opendocument.graphics-template',
             'application/vnd.oasis.opendocument.presentation',
             'application/vnd.oasis.opendocument.presentation-template',
             'application/vnd.oasis.opendocument.spreadsheet',
             'application/vnd.oasis.opendocument.spreadsheet-template']
MIMETYPES_IMAGES = ['image/png',
                    'image/jpeg',
                    'image/bmp',
                    'image/gif',
                    'image/tiff',
                    'image/x-tiff']
_ = str


def get_files(files_in):
    files = []
    for file_in in files_in:
        print(file_in)
        file_in = unquote_plus(file_in.get_uri()[7:])
        if os.path.isfile(file_in):
            files.append(file_in)
    return files


def extract_images(orginalFile):
    filename, fileextension = os.path.splitext(orginalFile)
    destFolder = '{0}_images'.format(filename)

    if os.path.exists(destFolder):
        shutil.rmtree(destFolder, True)
    os.makedirs(destFolder)

    with ZipFile(orginalFile, 'r') as myzip:
        for element in myzip.infolist():
            filename = element.filename.decode()
            if filename.startswith('Pictures/') and\
                    mimetypes.guess_type(
                        'file://' + filename)[0] in MIMETYPES_IMAGES:
                print(element.filename, type(element))
                name = element.filename[9:]
                unpacked = open(os.path.join(destFolder, name), 'w')
                unpacked.write(myzip.read(filename))
                unpacked.close()


class ProgressDialog(Gtk.Dialog):
    __gsignals__ = {
        'i-want-stop': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, title, parent, max_value):
        Gtk.Dialog.__init__(self, title, parent)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_size_request(330, 30)
        self.set_resizable(False)
        self.connect('destroy', self.close)
        self.set_modal(True)
        vbox = Gtk.VBox(spacing=5)
        vbox.set_border_width(5)
        self.get_content_area().add(vbox)
        #
        frame1 = Gtk.Frame()
        vbox.pack_start(frame1, True, True, 0)
        table = Gtk.Table(2, 2, False)
        frame1.add(table)
        #
        self.label = Gtk.Label()
        table.attach(self.label, 0, 2, 0, 1,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK,
                     yoptions=Gtk.AttachOptions.EXPAND)
        #
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_size_request(300, 0)
        table.attach(self.progressbar, 0, 1, 1, 2,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK,
                     yoptions=Gtk.AttachOptions.EXPAND)
        button_stop = Gtk.Button()
        button_stop.set_size_request(40, 40)
        button_stop.set_image(
            Gtk.Image.new_from_stock(Gtk.STOCK_STOP, Gtk.IconSize.BUTTON))
        button_stop.connect('clicked', self.on_button_stop_clicked)
        table.attach(button_stop, 1, 2, 1, 2,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK)
        self.stop = False
        self.show_all()
        self.max_value = max_value
        self.value = 0.0

    def emit(self, *args):
        GLib.idle_add(GObject.GObject.emit, self, *args)

    def set_max_value(self, anobject, max_value):
        self.max_value = float(max_value)

    def get_stop(self):
        return self.stop

    def on_button_stop_clicked(self, widget):
        self.stop = True
        self.emit('i-want-stop')

    def close(self, *args):
        self.destroy()

    def set_element(self, anobject, element):
        self.label.set_text(_('Compress: %s') % element)

    def increase(self, anobject, value):
        self.value += float(value)
        fraction = self.value / self.max_value
        self.progressbar.set_fraction(fraction)
        if self.value == self.max_value:
            self.hide()


class DoItInBackground(GObject.GObject, Thread):
    __gsignals__ = {
        'started': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (int,)),
        'ended': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (bool,)),
        'start_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (str,)),
        'end_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (int,)),
    }

    def __init__(self, elements):
        GObject.GObject.__init__(self)
        Thread.__init__(self)
        self.elements = elements
        self.stopit = False
        self.ok = True
        self.daemon = True
        self.process = None

    def emit(self, *args):
        GLib.idle_add(GObject.GObject.emit, self, *args)

    def stop(self, *args):
        self.stopit = True

    def extract_images(self, file_in):
        extract_images(file_in)

    def run(self):
        total = 0
        for element in self.elements:
            total += os.path.getsize(element)
        self.emit('started', total)
        try:
            for element in self.elements:
                print(element)
                if self.stopit is True:
                    self.ok = False
                    break
                self.emit('start_one', element)
                self.extract_images(element)
                self.emit('end_one', os.path.getsize(element))
        except Exception as e:
            self.ok = False
        try:
            if self.process is not None:
                self.process.terminate()
                self.process = None
        except Exception as e:
            print(e)
        self.emit('ended', self.ok)


class ExtImagesODTFileMenuProvider(GObject.GObject, FileManager.MenuProvider):
    """
    Implements the 'Replace in Filenames' extension to the File Manager\
    right-click menu
    """

    def __init__(self):
        """
        File Manager crashes if a plugin doesn't implement the __init__\
        method
        """
        mimetypes.init()
        pass

    def all_are_odt_files(self, items):
        for item in items:
            file_in = unquote_plus(item.get_uri()[7:])
            if not os.path.isfile(file_in):
                return False
            mimetype = mimetypes.guess_type('file://' + file_in)[0]
            if mimetype not in MIMETYPES:
                return False
        return True

    def extractimages(self, menu, selected, window):
        odtfiles = get_files(selected)
        diib = DoItInBackground(odtfiles)
        progreso = ProgressDialog(_('Compress ODT file'),
                                  window,
                                  len(odtfiles))
        diib.connect('started', progreso.set_max_value)
        diib.connect('start_one', progreso.set_element)
        diib.connect('end_one', progreso.increase)
        diib.connect('ended', progreso.close)
        progreso.connect('i-want-stop', diib.stop)
        diib.start()
        progreso.run()

    def get_file_items(self, window, sel_items):
        """
        Adds the 'Replace in Filenames' menu item to the File Manager\
        right-click menu, connects its 'activate' signal to the 'run'\
        method passing the selected Directory/File
        """
        top_menuitem = FileManager.MenuItem(
            name='ExtImagesODTFileMenuProvider::Gtk-extimaagesfodt-top',
            label=_('Extract images from LibreOffice files') + '...',
            tip=_('Tool to extract images from LibreOffice files'))
        submenu = FileManager.Menu()
        top_menuitem.set_submenu(submenu)

        sub_menuitem_00 = FileManager.MenuItem(
            name='ExtImagesODTFileMenuProvider::Gtk-extimaagesfodt-sub-00',
            label=_('Extract images from LibreOffice files'),
            tip=_('Tool to extract images from LibreOffice files'))
        if self.all_are_odt_files(sel_items):
            sub_menuitem_00.connect('activate',
                                    self.extractimages,
                                    sel_items,
                                    window)
        else:
            sub_menuitem_00.set_property('sensitive', False)
        submenu.append_item(sub_menuitem_00)

        sub_menuitem_02 = FileManager.MenuItem(
            name='ExtImagesODTFileMenuProvider::Gtk-extimaagesfodt-sub-02',
            label=_('About'),
            tip=_('About'))
        sub_menuitem_02.connect('activate', self.about, window)
        submenu.append_item(sub_menuitem_02)

        return top_menuitem,

    def about(self, widget, window):
        ad = Gtk.AboutDialog(parent=window)
        ad.set_name(APP)
        ad.set_version(VERSION)
        ad.set_copyright('Copyrignt (c) 2017\nLorenzo Carbonell')
        ad.set_comments(APP)
        ad.set_license('''
This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
''')
        ad.set_website('http://www.atareao.es')
        ad.set_website_label('http://www.atareao.es')
        ad.set_authors([
            'Lorenzo Carbonell <lorenzo.carbonell.cerezo@gmail.com>'])
        ad.set_documenters([
            'Lorenzo Carbonell <lorenzo.carbonell.cerezo@gmail.com>'])
        ad.set_icon_name(APP)
        ad.set_logo_icon_name(APP)
        ad.run()
        ad.destroy()


if __name__ == '__main__':
    files = ['/home/lorenzo/Escritorio/ODT samples/test1.odt',
             '/home/lorenzo/Escritorio/ODT samples/test2.odt',
             '/home/lorenzo/Escritorio/ODT samples/test3.odt',
             '/home/lorenzo/Escritorio/ODT samples/test4.odt',
             '/home/lorenzo/Escritorio/ODT samples/test5.odt']
    # reduce_lo_file(orginalFile)
    pd = ProgressDialog('Test', None, len(files))
    diib = DoItInBackground(files)
    diib.connect('started', pd.set_max_value)
    diib.connect('start_one', pd.set_element)
    diib.connect('end_one', pd.increase)
    diib.connect('ended', pd.close)
    pd.connect('i-want-stop', diib.stop)
    diib.run()
    #pd = ProgressDialog('Test', None, 5)
    pd.run()
