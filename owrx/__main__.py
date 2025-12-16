import logging

# the linter will complain about this, but the logging must be configured before importing all the other modules
# loglevel will be adjusted later, INFO is just for the startup

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from http.server import HTTPServer
from owrx.http import RequestHandler
from owrx.config.core import CoreConfig
from owrx.config import Config
from owrx.config.commands import MigrateCommand
from owrx.feature import FeatureDetector
from owrx.sdr import SdrService
from socketserver import ThreadingMixIn
from owrx.service import Services
from owrx.websocket import WebSocketConnection
from owrx.reporting import ReportingEngine
from owrx.version import openwebrx_version
from owrx.audio.queue import DecoderQueue
from owrx.admin import add_admin_parser, run_admin_action
from owrx.reporting import ReportingEngine
from owrx.markers import Markers
from owrx.gps import GpsUpdater
from datetime import datetime
from pathlib import Path
import signal
import argparse
import socket
import os.path
import ssl

class ThreadedHttpServer(ThreadingMixIn, HTTPServer):
    def __init__(self, web_port, RequestHandlerClass, use_ipv6, bind_address=None):
        if bind_address is None:
            bind_address = "::" if use_ipv6 else "0.0.0.0"
        if use_ipv6:
            self.address_family = socket.AF_INET6
        super().__init__((bind_address, web_port), RequestHandlerClass)


class SignalException(Exception):
    pass


def handleSignal(sig, frame):
    raise SignalException("Received Signal {sig}".format(sig=sig))


def reportServerState(state):
    pm = Config.get()
    if pm["report_radio"]:
        ReportingEngine.getSharedInstance().spot({
            "mode"      : "RX",
            "timestamp" : round(datetime.now().timestamp() * 1000),
            "version"   : openwebrx_version,
            "lat"       : pm["receiver_gps"]["lat"],
            "lon"       : pm["receiver_gps"]["lon"],
            "state"     : state
        })


def main():
    parser = argparse.ArgumentParser(description="OpenWebRX - Open Source SDR Web App for Everyone!")
    parser.add_argument(
        "-c",
        "--config",
        action="store",
        help="Read core configuration from specified file",
        metavar="configfile",
        type=Path,
    )
    parser.add_argument("-v", "--version", action="store_true", help="Show the software version")
    parser.add_argument("--debug", action="store_true", help="Set loglevel to DEBUG")

    moduleparser = parser.add_subparsers(title="Modules", dest="module")
    adminparser = moduleparser.add_parser("admin", help="Administration actions")
    add_admin_parser(adminparser)

    configparser = moduleparser.add_parser("config", help="Configuration actions")
    configcommandparser = configparser.add_subparsers(title="Commands", dest="command")

    migrateparser = configcommandparser.add_parser("migrate", help="Migrate configuration files")
    migrateparser.set_defaults(cls=MigrateCommand)

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.version:
        print("OpenWebRX+ version {version}".format(version=openwebrx_version))
        return 0

    CoreConfig.load(args.config)

    if args.module == "admin":
        return run_admin_action(adminparser, args)

    if args.module == "config":
        return run_admin_action(configparser, args)

    return start_receiver(loglevel=logging.DEBUG if args.debug else None)


def start_receiver(loglevel=None):
    print(
        """

OpenWebRX+ - Open Source SDR Web App for Everyone!  | for license see LICENSE file in the package
_________________________________________________________________________________________________

Author contact info:    Marat Fayzullin <luarvique@gmail.com>
Documentation:          https://github.com/jketterl/openwebrx/wiki
Support and info:       https://groups.io/g/openwebrx

        """,
        flush=True
    )

    logger.info("OpenWebRX+ version {0} starting up...".format(openwebrx_version))

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, handleSignal)

    coreConfig = CoreConfig()

    # passed loglevel takes priority (used for the --debug argument)
    logging.getLogger().setLevel(coreConfig.get_log_level() if loglevel is None else loglevel)

    # config warmup
    Config.validateConfig()

    featureDetector = FeatureDetector()
    failed = featureDetector.get_failed_requirements("core")
    if failed:
        logger.error(
            "you are missing required dependencies to run openwebrx. "
            "please check that the following core requirements are installed and up to date: %s",
            ", ".join(failed)
        )
        for f in failed:
            description = featureDetector.get_requirement_description(f)
            if description:
                logger.error("description for %s:\n%s", f, description)
        return 1

    # Get error messages about unknown / unavailable features as soon as possible
    # start up "always-on" sources right away
    SdrService.getAllSources()

    Services.start()

    # Instantiate and start GPS location updater
    GpsUpdater.init()

    # Instantiate and refresh marker database
    Markers.start()

    # Report server started
    reportServerState("ServerStarted")

    try:
        # This is our HTTP server
        server = ThreadedHttpServer(coreConfig.get_web_port(), RequestHandler, coreConfig.get_web_ipv6(), coreConfig.get_web_bind_address())
        # We expect to find SSL certificate here
        keyFile  = "/etc/openwebrx/key.pem"
        certFile = "/etc/openwebrx/cert.pem"
        # If SSL certificate found, use HTTPS instead of HTTP
        if os.path.isfile(keyFile) and os.path.isfile(certFile):
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certFile, keyFile)
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
            logger.info("Found SSL certificate, using https:// protocol.")
        else:
            logger.info("No SSL certificate, using http:// protocol.")
            logger.info("To enable https://, supply SSL certificate:")
            logger.info("    " + certFile)
            logger.info("    " + keyFile)
        # Run the server
        logger.info("Ready to serve requests.")
        server.serve_forever()
    except SignalException:
        pass

    WebSocketConnection.closeAll()
    Markers.stop()
    GpsUpdater.stop()
    Services.stop()
    SdrService.stopAllSources()
    DecoderQueue.stopAll()

    # Report server stopped
    reportServerState("ServerStopped")

    # Done with reporting now
    ReportingEngine.stopAll()

    return 0
