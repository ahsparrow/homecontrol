from datetime import datetime, timedelta
import json
import time
import urllib.request

import gevent

from .suntime import Sun

LAT = 51.0
LON = -1.6

SWITCH_OFF = 0
SWITCH_ON = 255

class SunEvent:
    # offset is datetime.timedelta object
    def __init__(self, sun, offset):
        self.sun = sun
        self.offset = offset

    def __gt__(self, secs):
        dt = datetime.utcfromtimestamp(secs) - timedelta(seconds=self.offset)
        return self.suntime() > dt.time()

class SunriseEvent(SunEvent):
    def suntime(self):
        return self.sun.get_sunrise_time().time()

    def asdict(self):
        return {'type': "sunrise", 'offset': self.offset}

class SunsetEvent(SunEvent):
    def suntime(self):
        return self.sun.get_sunset_time().time()

    def asdict(self):
        return {'type': "sunset", 'offset': self.offset}

class DailyEvent:
    # localtime is naive datetime.time object
    def __init__(self, localtime):
        self.localtime = localtime

    def __gt__(self, secs):
        dt = datetime.fromtimestamp(secs)
        return self.localtime > dt.time()

    def asdict(self):
        return {'type': "daily",
                'time': self.localtime.strftime("%H:%M:%S")}

class Timer:
    def __init__(self, on_event, off_event):
        self.on_event = on_event
        self.off_event = off_event

    def is_on(self, secs):
        return (not (self.on_event > secs)) and (self.off_event > secs)

    def asdict(self):
        return {'on': self.on_event.asdict(), 'off': self.off_event.asdict()}

class Controller:
    def __init__(self, resolution=60):
        self.resolution = resolution

        self.switches = {}
        self.sun = Sun(LAT, LON)

        self.secs = int(time.time())

    def load(self, settings):
        for name, switch in settings.items():
            self.switches[name] = {
                    'timers': [self.timer_factory(t) for t in switch['timers']],
                    'mode': switch['mode']}

    def dump(self):
        result = {}
        for name, switch in self.switches.items():
            result[name] = {'mode': switch['mode'],
                            'timers': [t.asdict() for t in switch['timers']]}

        return result

    def timer_factory(self, tim):
        on_event = self.event_factory(tim['on'])
        off_event = self.event_factory(tim['off'])

        return Timer(on_event, off_event)

    def event_factory(self, evt):
        if evt['type'] == 'daily':
            localtime = datetime.strptime(evt['time'], "%H:%M:%S").time()
            event = DailyEvent(localtime)

        elif evt['type'] == 'sunrise':
            event = SunriseEvent(self.sun, evt['offset'])

        elif evt['type'] == 'sunset':
            event = SunsetEvent(self.sun, evt['offset'])

        return event

    def set_switch(self, switch, mode):
        self.switches[switch]['mode'] = mode
        if mode == 'manual':
            return
        elif mode == 'on':
            val = 'on'
        elif mode == 'auto':
            val = self._get_auto_setting(switch, self.secs)
        else:
            val = 'off'

        self._set_switch(switch, val)

    def start(self):
        self.secs = int(time.time()) + 1
        while 1:
            delta = self.secs - time.time()
            if delta > 0:
                gevent.sleep(delta)

            if (self.secs % self.resolution) == 0:
                self._update(self.secs)
            self.secs += 1

    # _update is called every self.resolution seconds
    def _update(self, secs):
        for s, switch in self.switches.items():
            if switch['mode'] == 'manual':
                continue
            elif switch['mode'] == 'on':
                setting = 'on'
            elif switch['mode'] == 'off':
                setting = 'off'
            else:
                setting = self._get_auto_setting(switch['timers'], secs)

            self._set_switch(s, setting)

    def _get_auto_setting(self, timers, secs):
        on = False
        for t in timers:
            on = on or t.is_on(secs)

        val = 'on' if on else 'off'
        return val

    def _set_switch(self, switch, setting):
        print(datetime.now(), switch, setting)
        url = "http://homeweb:5000/api/switch/%s" % switch
        data = json.dumps(SWITCH_ON if setting == 'on' else SWITCH_OFF).encode('utf-8')
        req = urllib.request.Request(url=url, data=data, method='PUT',
                headers={'Content-Type': "application/json"})

        try:
            urllib.request.urlopen(req)
        except urllib.error.URLError:
            print("Error openning " + url)
