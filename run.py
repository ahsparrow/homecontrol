from gevent import monkey; monkey.patch_all()
import gevent

if __name__ == "__main__":
    import argparse
    import datetime
    import yaml

    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", help="Configuration file",
                        type=argparse.FileType("r"))
    parser.add_argument("-r", "--resolution", default=600, type=int,
                        help="Event resolution (secs)")
    parser.add_argument("-z", "--zhost", default="localhost",
                        help="Z-Wave host")
    parser.add_argument("-p", "--zport", type=int, default=5000,
                        help="Z-Wave port")
    args = parser.parse_args()

    from controller.controller import Controller

    config = yaml.safe_load(args.config_file)
    c = Controller(resolution=args.resolution,
                   zhost=args.zhost, zport=args.zport)
    c.load(config)

    g = gevent.spawn(Controller.start, c)
    gevent.joinall([g])
