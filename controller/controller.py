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

class Timer:
    def __init__(self, setting):
        self.setting = setting

class SunTimer(Timer):
    # offset is datetime.timedelta object
    def __init__(self, setting, sun, offset):
        super().__init__(setting)
        self.sun = sun
        self.offset = offset

    def __le__(self, secs):
        dt = datetime.utcfromtimestamp(secs) - timedelta(seconds=self.offset)
        return self.suntime() <= dt.time()

class SunriseTimer(SunTimer):
    def suntime(self):
        return self.sun.get_sunrise_time().time()

class SunsetTimer(SunTimer):
    def suntime(self):
        return self.sun.get_sunset_time().time()

class DailyTimer(Timer):
    # localtime is naive datetime.time object
    def __init__(self, setting, localtime):
        super().__init__(setting)
        self.localtime = localtime

    def __le__(self, secs):
        dt = datetime.fromtimestamp(secs)
        return self.localtime <= dt.time()

class Controller:
    def __init__(self, resolution=60):
        self.resolution = resolution

        self.switches = {}
        self.sun = Sun(LAT, LON)

        self.secs = int(time.time())
        self.timer_id = 0

    def load(self, settings):
        for name, switch in settings.items():
            self.switches[name] = {
                    'timers': [self.timer_factory(t) for t in switch['timers']],
                    'mode': switch['mode']}

    def timer_factory(self, tim):
        if tim['type'] == 'daily':
            localtime = datetime.strptime(tim['time'], "%H:%M:%S").time()
            timer = DailyTimer(tim['setting'], localtime)

        elif tim['type'] == 'sunrise':
            timer = SunriseTimer(tim['setting'], self.sun, tim['offset'])

        elif tim['type'] == 'sunset':
            timer = SunsetTimer(tim['setting'], self.sun, tim['offset'])

        return timer

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
                setting = self._get_auto_setting(s, secs)

            self._set_switch(s, setting)

    def _get_auto_setting(self, switch, secs):
        acc = 0
        for t in self.switches[switch]['timers']:
            if t <= secs:
                acc += 1 if t.setting == 'on' else -1

        val =  'on' if acc > 0 else 'off'
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
