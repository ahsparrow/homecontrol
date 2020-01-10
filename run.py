from gevent import monkey; monkey.patch_all()
import gevent

import datetime
import yaml

from controller.controller import Controller, DailyTimer, SunsetTimer, SunriseTimer

c = Controller(resolution=10)

with open('config.yaml') as f:
    config = yaml.safe_load(f)

c.load(config)

g = gevent.spawn(Controller.start, c)
gevent.joinall([g])
