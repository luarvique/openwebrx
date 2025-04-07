from owrx.config.core import CoreConfig
from datetime import datetime
from random import randint

import random
import urllib
import threading
import logging
import json
import os
import time

logger = logging.getLogger(__name__)

class WebAgent(object):
    def __init__(self, dataName: str):
        self.refreshPeriod = 60*60*24
        self.lock = threading.Lock()
        self.event = threading.Event()
        self.thread = None
        self.dataName = dataName
        self.errorCount = 0
        self.maxErrors = 5
        self.data = self.loadData(self._getCachedDatabaseFile())
        self.freshData = False

    # Get name of the cached database file
    def _getCachedDatabaseFile(self):
        return "{0}/{1}".format(CoreConfig().get_data_directory(), self.dataName)

    # Fake generic User-Agent, since at least KiwiSDR website likes that
    def _openUrl(self, url: str):
        hdrs = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/" + str(randint(100, 135)) + ".0" }
        req  = urllib.request.Request(url, headers = hdrs)
        return urllib.request.urlopen(req)

    # Return the current data
    def getAll(self):
        with self.lock:
            return self.data.copy()

    # Check if there is freshly downloaded data
    def hasFreshData(self):
        with self.lock:
            result = self.freshData
            self.freshData = False
            return result

    # Get last downloaded timestamp or 0 for none
    def lastDownloaded(self):
        try:
            file = self._getCachedDatabaseFile()
            if os.path.isfile(file) and os.path.getsize(file) > 0:
                return os.path.getmtime(file)
            else:
                return 0
        except Exception as e:
            return 0

    # Start the main thread
    def startThread(self):
        if self.thread is None:
            logger.info("Starting {0} database thread.".format(type(self).__name__))
            self.event.clear()
            self.thread = threading.Thread(target=self._refreshThread, name=type(self).__name__)
            self.thread.start()

    # Stop the main thread
    def stopThread(self):
        if self.thread is not None:
            logger.info("Stopping {0} database thread.".format(type(self).__name__))
            self.event.set()
            self.thread.join()
            self.thread = None

    # This is the actual thread function
    def _refreshThread(self):
        # Random time to refresh data
        refreshMinute = random.randint(5, 49)
        # Main Loop
        while not self.event.is_set():
            # Wait until the check-and-update time
            waitMinutes = refreshMinute - datetime.utcnow().minute
            waitMinutes = waitMinutes + 60 if waitMinutes <= 0 else waitMinutes
            self.event.wait(waitMinutes * 60)
            # Check if we need to exit
            if self.event.is_set():
                break
            # Check and refresh cached database as needed
            self.refresh()
        # Done with the thread
        self.thread = None

    # Refresh database from the web.
    def refresh(self):
        # This file contains cached receivers database
        file = self._getCachedDatabaseFile()
        # If cached database is stale...
        if self.errorCount < self.maxErrors and time.time() - self.lastDownloaded() >= self.refreshPeriod:
            logger.info("Updating {0} database from web (attempt {1}/{2})...".format(type(self).__name__, self.errorCount + 1, self.maxErrors))
            # Load receivers list from the web
            data = self._loadFromWeb()
            if data is None:
                # Count continuous errors
                self.errorCount += 1
            else:
                # Clear error count
                self.errorCount = 0
                # Save parsed data into a file
                self.saveData(file, data)
                # Update current database
                with self.lock:
                    self.data = data
                    self.freshData = True
                return True
        # No refresh done
        return False

    # Save database to a given JSON file.
    def saveData(self, file: str, data):
        logger.info("Saving {0} items to '{1}'...".format(len(data), file))
        try:
            with open(file, "w") as f:
                json.dump(data, f, indent=2)
                f.close()
        except Exception as e:
            logger.error("saveData() exception: {0}".format(e))

    # Load database from a given JSON file.
    def loadData(self, file: str):
        logger.info("Loading items from '{0}'...".format(file))
        if not os.path.isfile(file):
            result = []
        else:
            try:
                with open(file, "r") as f:
                    result = json.load(f)
                    f.close()
            except Exception as e:
                logger.error("loadData() exception: {0}".format(e))
                result = []
        # Done
        logger.info("Loaded {0} items from '{1}'...".format(len(result), file))
        return result

    # Scrape web site(s) for data
    def _loadFromWeb(self):
        # Fill in your own method
        return []
