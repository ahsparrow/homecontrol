from datetime import datetime, timedelta
import json
import time
import urllib.request

import gevent

from .suntime import Sun

LAT = 51.0
LON = -1.6

SWITCH_ON = 1
SWITCH_OFF = -1

class Timer:
    def __init__(self, delta):
        self.delta = delta

class SunTimer(Timer):
    # offset is datetime.timedelta object
    def __init__(self, offset, delta):
        super().__init__(delta)
        self.offset = offset
        self.sun = Sun(LAT, LON)

class SunriseTimer(SunTimer):
    def __le__(self, secs):
        sunrise = self.sun.get_sunrise_time()
        dt = datetime.utcfromtimestamp(secs) - timedelta(seconds=self.offset)
        return sunrise.time() <= dt.time()

class SunsetTimer(SunTimer):
    def __le__(self, secs):
        sunset = self.sun.get_sunset_time()
        dt = datetime.utcfromtimestamp(secs) - timedelta(seconds=self.offset)
        return sunset.time() <= dt.time()

class DailyTimer(Timer):
    # localtime is naive datetime.time object
    def __init__(self, localtime, delta):
        super().__init__(delta)
        self.localtime = localtime

    def __le__(self, secs):
        dt = datetime.fromtimestamp(secs)
        return self.localtime <= dt.time()

class Controller:
    def __init__(self, switches, resolution=60):
        self.switches = {s[0]: {'mode': 'manual', 'timers': {}, 'value': s[1]} for s in switches}
        self.resolution = resolution

        self.secs = int(time.time())
        self.timer_id = 0

    def set_switch(self, switch, mode):
        self.switches[switch]['mode'] = mode
        if mode == 'manual':
            return
        elif mode == 'on':
            val = self.switches[switch]['value']
        elif mode == 'auto':
            val = self._get_auto_value(switch, self.secs)
        else:
            val = 0

        self._set_switch(switch, val)

    def add_timer(self, timer, switch):
        self.timer_id += 1
        self.switches[switch]['timers'][self.timer_id] = timer
        return self.timer_id

    def remove_timer(self, timer_id):
        pass

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
                value = switch['value']
            elif switch['mode'] == 'off':
                value = 0
            else:
                value = self._get_auto_value(s, secs)

            self._set_switch(s, value)

    def _get_auto_value(self, switch, secs):
        acc = 0
        for t in self.switches[switch]['timers'].values():
            if t <= secs:
                acc += t.delta

        val =  self.switches[switch]['value'] if acc > 0 else 0
        return val

    def _set_switch(self, switch, value):
        print(datetime.now(), switch, value)
        url = "http://homeweb:5000/api/switch/%s" % switch
        data = json.dumps(value).encode('utf-8')
        req = urllib.request.Request(url=url, data=data, method='PUT',
                headers={'Content-Type': "application/json"})

        try:
            urllib.request.urlopen(req)
        except urllib.error.URLError:
            print("Error openning " + url)
