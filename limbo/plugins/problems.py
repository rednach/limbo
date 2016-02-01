import sys
import time

from mk_livestatus import Socket

ANSIBLE_COLOR=True
if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
    ANSIBLE_COLOR=False
else:
    try:
        import curses
        curses.setupterm()
        if curses.tigetnum('colors') < 0:
            ANSIBLE_COLOR=False
    except ImportError:
        # curses library was not found
        pass
    except curses.error:
        # curses returns an error (e.g. could not find terminal)
        ANSIBLE_COLOR=False


class HostService(object):
    STATE2STRING = {}

    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k, kwargs[k])
        self.init()


    def init(self):
        self.state_id = self.state
        self.state = self.STATE2STRING.get(self.state_id)


class Host(HostService):
    STATE2STRING = {0: 'UP', 1: 'DOWN'}

    def init(self):
    	super(self.__class__, self).init()
        self.host_name = self.name
        self.service = ''


class Service(HostService):
    STATE2STRING = {0: 'OK', 1: 'WARNING', 2: 'CRITICAL', 3: 'UNKNOWN'}

    def init(self):
    	super(self.__class__, self).init()
        self.host_name = self.host_name
        self.service = ''


# --- begin "pretty"
#
# pretty - A miniature library that provides a Python print and stdout
# wrapper that makes colored terminal text easier to use (eg. without
# having to mess around with ANSI escape sequences). This code is public
# domain - there is no license except that you must leave this header.
#
# Copyright (C) 2008 Brian Nez <thedude at bri1 dot com>
#
# http://nezzen.net/2008/06/23/colored-text-in-python-using-ansi-escape-sequences/

codeCodes = {
    'black':     '0;30', 'bright gray':    '0;37',
    'blue':      '0;34', 'white':          '1;37',
    'green':     '0;32', 'bright blue':    '1;34',
    'cyan':      '0;36', 'bright green':   '1;32',
    'red':       '0;31', 'bright cyan':    '1;36',
    'purple':    '0;35', 'bright red':     '1;31',
    'yellow':    '0;33', 'bright purple':  '1;35',
    'dark gray': '1;30', 'bright yellow':  '1;33',
    'normal':    '0'
}

def stringc(text, color):
    """String in color."""

    if ANSIBLE_COLOR:
        return "\033["+codeCodes[color]+"m"+text+"\033[0m"
    else:
        return text

# --- end "pretty"


format_parameters = dict(
    width_aleascope_name=38,
    width_ip = 16,
    width_type = 15,
    width_model = 13,

    width_name=16,
    width_output=60,
    width_duration=17,
    width_header=18,
    state2color = {1:'yellow', 2:'red', 3:'blue'},
)

HOSTCOLUMNS = ('name', 'state', 
    'last_check', 'next_check', 
    'acknowledged', 
    'plugin_output', 
    'source_problems', 
    'is_impact', 'is_flapping', 'is_problem', 
    'scheduled_downtime_depth', 
    'downtimes', 'comments', 'business_impact', 
    'scheduled_downtime_depth', 'num_services_crit', 
    'num_services_warn', 'num_services_unknown', 'num_services_ok', 
    'has_been_checked', 'got_business_rule', 'hard_state', 'initial_state')

SERVICECOLUMNS = ('host_name', 'description', 'state', 'last_check', 'next_check', 'acknowledged', 'plugin_output', 'source_problems', 'is_impact', 'is_flapping', 'is_problem', 'scheduled_downtime_depth', 'downtimes', 'comments', 'business_impact')

def print_duration(t, just_duration=False, x_elts=0):
    if t == 0 or t == None:
        return 'N/A'
    #print "T", t
    # Get the difference between now and the time of the user
    seconds = int(time.time()) - int(t)

    # If it's now, say it :)
    if seconds == 0:
        return 'Now'

    in_future = False

    # Remember if it's in the future or not
    if seconds < 0:
        in_future = True

    # Now manage all case like in the past
    seconds = abs(seconds)
    #print "In future?", in_future

    #print "sec", seconds
    seconds = long(round(seconds))
    #print "Sec2", seconds
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    weeks, days = divmod(days, 7)
    months, weeks = divmod(weeks, 4)
    years, months = divmod(months, 12)

    minutes = long(minutes)
    hours = long(hours)
    days = long(days)
    weeks = long(weeks)
    months = long(months)
    years = long(years)

    duration = []
    if years > 0:
        duration.append('%dy' % years)
    else:
        if months > 0:
            duration.append('%dM' % months)
        if weeks > 0:
            duration.append('%dw' % weeks)
        if days > 0:
            duration.append('%dd' % days)
        if hours > 0:
            duration.append('%dh' % hours)
        if minutes > 0:
            duration.append('%dm' % minutes)
        if seconds > 0:
            duration.append('%ds' % seconds)

    #print "Duration", duration
    # Now filter the number of printed elements if ask
    if x_elts >= 1:
        duration = duration[:x_elts]

    # Maybe the user just want the duration
    if just_duration:
        return ' '.join(duration)

    # Now manage the future or not print
    if in_future:
        return 'in ' + ' '.join(duration)
    else:  # past :)
        return ' '.join(duration) + ' ago'


def on_message(msg, server):
    text = msg.get("text", "")

    s = Socket(('ses', 42000))
    q = s.hosts.columns(*HOSTCOLUMNS).filter('state != 0')
    format_sting = ''
    for p in q.call():
        h = Host(**p)
        format_sting += _print_item(h) + '\n'

    q = s.services.columns(*SERVICECOLUMNS).filter('state != 0')
    for p in q.call():
        s = Service(**p)
        format_sting += _print_item(h) + '\n'

    return str(msg) + '\n\n' + format_sting


def _print_item(item, show_plugin_output_if_ok=True):
    show_extra_fields = item.state or show_plugin_output_if_ok
    string = '{}{}{}{} {:{left_align}{width_name}} {:{left_align}{width_name}} {:>{width_output}.{width_output}} {:>{width_duration}} {:>{width_duration}} '.format(
        'v' if item.acknowledged else ' ',
        'f' if item.is_flapping else ' ',
        'p' if item.is_problem else ' ',
        'i' if item.is_impact else ' ',
        item.host_name,
        item.service,
        item.plugin_output if show_extra_fields else '',
        print_duration(item.last_check) if show_extra_fields else '',
        print_duration(item.next_check) if show_extra_fields else '',
        left_align='<' if 'ost' in str(item.__class__) else '>',
        width_name=format_parameters['width_name'],
        width_output=format_parameters['width_output'],
        width_duration=format_parameters['width_duration'],
        )
    return string
    # return stringc(string, color=format_parameters['state2color'].get(item.state_id, 'normal'))


if __name__ == '__main__':
    # ret = on_message({}, None)
    # print ret
    pass
