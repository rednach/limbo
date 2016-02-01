import os
import sys
import time
import re

from mk_livestatus import Socket
from slacker import Slacker

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
        self.service = self.description


HOSTCOLUMNS = ('name', 'state', 'last_check', 'next_check', 'acknowledged', 'plugin_output', 'source_problems', 'is_impact', 'is_flapping', 'is_problem', 'scheduled_downtime_depth', 'downtimes', 'comments', 'business_impact', 'scheduled_downtime_depth', 'num_services_crit', 'num_services_warn', 'num_services_unknown', 'num_services_ok', 'has_been_checked', 'got_business_rule', 'hard_state', 'initial_state')
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
    print 'text', text

    match = re.findall(r"!(?:problems|pbl) (.*)", text)
    if not match:
        return

    channel = msg.get("channel", "")
    user = msg.get("user", "")
    sufix = match[0]

    if not (channel or user):
        return

    if channel and channel.startswith('C'):
        slack = _get_slacker()
        response = slack.channels.list()
        try:
            channel_name, = [chn['name'] for chn in response.body['channels'] if chn['id'] == channel]
        except Exception, exc:
            for chn in response.body['channels']:
                if chn['id'] == channel:
                    print '!!!', channel
                else:
                    print '???', chn['id'], channel

            return 'Exception:' + str(exc)+'-'+str(msg)+'-'
    elif sufix:
        channel_name = sufix
    else:
        return 'for which net?'

    s = Socket(('%s.phicus.es' % channel_name, 4299))
    try:
        q = s.hosts.columns(*HOSTCOLUMNS).filter('state != 0')
        format_sting = ''
        for p in q.call():
            format_sting += _slackize(Host(**p)) + '\n'

        format_sting += '\n'
        q = s.services.columns(*SERVICECOLUMNS).filter('state != 0')
        for p in q.call():
            format_sting += _slackize(Service(**p)) + '\n'
    except Exception, exc:
        return 'Exception channel_name=%s exc=%s' % (channel_name, str(exc))

    # return str(msg) + '\n\n' + format_sting
    return format_sting


def _get_slacker():
    return Slacker(os.environ.get('SLACK_TOKEN'))


def _slackize(item):
    servicestate2icon = {
        "UP": ":white_check_mark:",
        "DOWN": ":exclamation:",

        "CRITICAL": ":exclamation:",
        "WARNING": ":warning:",
        "OK": ":white_check_mark:",
        "UNKNOWN": ":question:",
    }
    icon = servicestate2icon.get(item.state, ':white_medium_square:')
    show_extra_fields = item.state or show_plugin_output_if_ok
    string = '{} {} {} {} {} {} {} '.format(
        icon,
        item.host_name,
        item.service,
        item.state,
        item.plugin_output,
        print_duration(item.last_check) if show_extra_fields else '',
        print_duration(item.next_check) if show_extra_fields else '',
        )
    return string

if __name__ == '__main__':
    ret = on_message({u'channel': u'C0BJR8H53', u'text': u'!pbl ses'}, None)
    print ret
