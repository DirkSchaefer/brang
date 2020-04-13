import threading
import logging
import datetime

import flask
from werkzeug.serving import make_server

log = logging.getLogger(__name__)


class ServerThread(threading.Thread):

    def __init__(self, app):
        threading.Thread.__init__(self)
        self.srv = make_server('127.0.0.1', 5000, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        log.info('starting server')
        self.srv.serve_forever()

    def shutdown(self):
        self.srv.shutdown()


def start_server():
    global server
    app = flask.Flask('test_app')

    @app.route('/changing/')
    def changing():
        """
        This mimics a website that is always changing.
        :return:
        """
        s = datetime.datetime.now().isoformat()
        return s

    @app.route('/fix/')
    def fix():
        """
        This mimics a website that never changes.
        :return:
        """
        return "void"

    server = ServerThread(app)
    server.start()
    log.info('server started')


def stop_server():
    global server
    server.shutdown()
    log.info('server shutdown')

