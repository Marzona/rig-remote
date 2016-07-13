#!/usr/bin/env python

"""
Remote application that interacts with rigs using rigctl protocol.
Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation
Author: Rafael Marmelo
Author: Simone Marzona
License: MIT License
Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2016 Tim Sweeney
TAS - Tim Sweeney - mainetim@gmail.com
2016/05/04 - TAS - Moved frequency_pp and frequency_pp_parse here.
2016/05/07 - TAS - Moved is_valid_hostname and is_valid_port here.
2016/05/08 - TAS - Added this_file_exists.
2016/05/30 - TAS - Added process_path.
"""

import re
from socket import gethostbyname, gaierror
import logging
import Tkinter as tk
import os.path
import ttk

logger = logging.getLogger(__name__)

# function definition

def khertz_to_hertz(value):
    return value*1000

def dbfs_to_sgn(value):
    return value*10

def frequency_pp(frequency):
    """Filter invalid chars and add thousands separator.
    :param frequency: frequency value
    :type frequency: string
    :return: frequency with separator
    :return type: string
    """

    return '{:,}'.format(int(re.sub("[^0-9]", '', frequency)))


def frequency_pp_parse(frequency):
    """Remove thousands separator and check for invalid chars.
    :param frequency: frequency value
    :type frequency: string
    :return: frequency without separator or None if invalid chars present
    :return type: string or None
    """
    if not isinstance(frequency, basestring):
        logger.error("frequency is not a string, "\
                     "but {}".format(type(frequency)))
        raise ValueError
    nocommas = frequency.replace(',', '')
    results = re.search("[^0-9]", nocommas)
    if results == None:
        return (nocommas)
    else:
        return (None)


def is_valid_port(port):
    """Checks if the provided port is a valid one.
    :param: port to connect to
    :type port: str as provided by tkinter
    :raises: ValueError if the string can't be converted to integer and
    if the converted ingeger is lesser than 2014 (privileged port)
    """

    try:
        int(port)
    except ValueError:
        logger.error("Incorrect data: port number must be int.")
        raise
    if int(port) <= 1024:
        logger.error("Privileged port used: {}".format(port))
        raise ValueError

def is_valid_hostname(hostname):
    """ Checks if hostname is truly a valid FQDN, or IP address.
    :param hostname:
    :type hostname: str
    :raises: ValueError if hostname is empty string
    :raises: Exception based on result of gethostbyname() call
    """

    if hostname == '':
        raise ValueError
    try:
        address = gethostbyname(hostname)
    except gaierror as e:
        logger.error("Hostname error: {}".format(e))
        raise

def this_file_exists(filename):
    """Test if a file will open.
    :param filename:
    :type filename: str
    :returns: filename if open was successful, None otherwise
    """
    try:
        with open(filename) as f:
            f.close()
            return(filename)
    except IOError:
        return None

def process_path(path):
    """Handle tilde expansion in a path.
    """

    working_path, working_name = os.path.split(path)
    if working_path:
        working_path = os.path.expanduser(working_path)
    return os.path.join(working_path, working_name)

class ToolTip:
    def __init__(self, master, text='', delay=1500, **opts):
        self.master = master
        self._opts = {'anchor':'center',
                      'bd':1,
                      'bg':'lightyellow',
                      'delay':delay,
                      'fg':'black',
                      'follow_mouse':0,
                      'font':None,
                      'justify':'left',
                      'padx':4,
                      'pady':2,
                      'relief':'solid',
                      'state':'normal',
                      'text':text,
                      'textvariable':None,
                      'width':0,
                      'wraplength':150}
        self.configure(**opts)
        self._tipwindow = None
        self._id = None
        self._id1 = self.master.bind("<Enter>", self.enter, '+')
        self._id2 = self.master.bind("<Leave>", self.leave, '+')
        self._id3 = self.master.bind("<ButtonPress>", self.leave, '+')
        self._follow_mouse = 0
        if self._opts['follow_mouse']:
            self._id4 = self.master.bind("<Motion>", self.motion, '+')
            self._follow_mouse = 1

    def configure(self, **opts):
        for key in opts:
            if self._opts.has_key(key):
                self._opts[key] = opts[key]
            else:
                KeyError = 'KeyError: Unknown option: "%s"' %key
                raise KeyError

    """
    these methods handle the callbacks on "<Enter>", "<Leave>" and "<Motion>"
    events on the parent widget; override them if you want to change the 
    widget's behavior
    """

    def enter(self, event=None):
        self._schedule()

    def leave(self, event=None):
        self._unschedule()
        self._hide()

    def motion(self, event=None):
        if self._tipwindow and self._follow_mouse:
            x, y = self.coords()
            self._tipwindow.wm_geometry("+%d+%d" % (x, y))

    """
    ------the methods that do the work:
    """

    def _schedule(self):
        self._unschedule()
        if self._opts['state'] == 'disabled':
            return
        self._id = self.master.after(self._opts['delay'], self._show)

    def _unschedule(self):
        id = self._id
        self._id = None
        if id:
            self.master.after_cancel(id)

    def _show(self):
        if self._opts['state'] == 'disabled':
            self._unschedule()
            return
        if not self._tipwindow:
            self._tipwindow = tw = tk.Toplevel(self.master)
            # hide the window until we know the geometry
            tw.withdraw()
            tw.wm_overrideredirect(1)

            if tw.tk.call("tk", "windowingsystem") == 'aqua':
                tw.tk.call("::tk::unsupported::MacWindowStyle",
                           "style",
                           tw._w,
                           "help",
                           "none")

            self.create_contents()
            tw.update_idletasks()
            x, y = self.coords()
            tw.wm_geometry("+%d+%d" % (x, y))
            tw.deiconify()

    def _hide(self):
        tw = self._tipwindow
        self._tipwindow = None
        if tw:
            tw.destroy()
                
    ##----these methods might be overridden in derived classes:

    def coords(self):
        # The tip window must be completely outside the master widget;
        # otherwise when the mouse enters the tip window we get
        # a leave event and it disappears, and then we get an enter
        # event and it reappears, and so on forever :-(
        # or we take care that the mouse pointer is always outside the tipwindow :-)
        tw = self._tipwindow
        twx, twy = tw.winfo_reqwidth(), tw.winfo_reqheight()
        w, h = tw.winfo_screenwidth(), tw.winfo_screenheight()
        # calculate the y coordinate:
        if self._follow_mouse:
            y = tw.winfo_pointery() + 20
            # make sure the tipwindow is never outside the screen:
            if y + twy > h:
                y = y - twy - 30
        else:
            y = self.master.winfo_rooty() + self.master.winfo_height() + 3
            if y + twy > h:
                y = self.master.winfo_rooty() - twy - 3
        # we can use the same x coord in both cases:
        x = tw.winfo_pointerx() - twx / 2
        if x < 0:
            x = 0
        elif x + twx > w:
            x = w - twx
        return x, y

    def create_contents(self):
        opts = self._opts.copy()
        for opt in ('delay', 'follow_mouse', 'state'):
            del opts[opt]
        label = tk.Label(self._tipwindow, **opts)
        label.pack()


class RCCheckbutton(ttk.Checkbutton) :
    """
    RCCheckbutton is derived from ttk.Checkbutton, and adds an 
    "is_checked" method to simplify checking instance's state, and
    new methods to return string state values for config file.
    """
    def __init__(self,*args,**kwargs) :
        self.var = kwargs.get('variable', tk.BooleanVar())
        kwargs['variable'] = self.var
        ttk.Checkbutton.__init__(self, *args, **kwargs)

    def is_checked(self) :
        return self.var.get()

    def get_str_val(self) :
        if self.is_checked() :
            return ("true")
        else :
            return ("false")

    def set_str_val(self, value) :
        if value.lower() in ("true", "t") :
            self.var.set(True)
        else :
            self.var.set(False)
