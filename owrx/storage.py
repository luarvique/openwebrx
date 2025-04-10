from owrx.config.core import CoreConfig
from owrx.config import Config
from datetime import datetime

import threading
import subprocess
import os
import re

import logging

logger = logging.getLogger(__name__)

class Storage(object):
    sharedInstance = None
    creationLock = threading.Lock()
    filePattern = r'[A-Z0-9]+-[0-9]+-[0-9]+(-[0-9]+)?(-[0-9]+)?\.(bmp|png|txt|mp3)'

    # Get shared instance of Storage class
    @staticmethod
    def getSharedInstance():
        with Storage.creationLock:
            if Storage.sharedInstance is None:
                Storage.sharedInstance = Storage()
        return Storage.sharedInstance

    # Construct an instance of Storage class
    def __init__(self):
        self.lock = threading.Lock()

    # Create stored file by name, modifying the name if the file exists
    def newFile(self, fileName: str, buffering: int = -1):
        filePath = self.getFilePath(fileName)

        with self.lock:
            if not os.path.exists(filePath):
                return open(filePath, "wb", buffering = buffering)
            elif "." in filePath:
                filePathX = "-{0}.".join(filePath.rsplit(".", 1))
                for i in range(99):
                    filePath1 = filePathX.format(i + 1)
                    if not os.path.exists(filePath1):
                        return open(filePath1, "wb", buffering = buffering)

        raise FileExistsError("File '{0}' already exists.".format(filePath))

    # Delete stored file by name, the name must match pattern
    def deleteFile(self, fileName: str):
        if re.match(self.filePattern, fileName):
            filePath = self.getFilePath(fileName)
            logger.info("Deleting '{0}'.".format(filePath))
            with self.lock:
                try:
                    os.unlink(filePath)
                except Exception as e:
                    logger.debug("deleteFile(): " + str(e))

    # Get list of stored files, sorted in reverse alphabetic order
    # (so that newer files appear first)
    def getStoredFiles(self):
        dir = CoreConfig().get_temporary_directory()
        with self.lock:
            files = [os.path.join(dir, f) for f in os.listdir(dir) if re.match(self.filePattern, f)]
        files.sort(key=lambda x: os.path.getctime(x), reverse=True)
        return [os.path.basename(f) for f in files]

    # Delete all stored files except for <keep_files> newest ones
    def cleanStoredFiles(self):
        pm    = Config.get()
        keep  = pm["keep_files"]
        dir   = CoreConfig().get_temporary_directory()

        with self.lock:
            files = [os.path.join(dir, f) for f in os.listdir(dir) if re.match(self.filePattern, f)]
            files.sort(key=lambda x: os.path.getctime(x), reverse=True)

            for f in files[keep:]:
                logger.debug("Deleting stored file '%s'." % os.path.basename(f))
                try:
                    os.unlink(f)
                except Exception as e:
                    logger.debug("cleanStoredFiles(): " + str(e))

    # Get file name pattern
    @staticmethod
    def getNamePattern():
        return Storage.filePattern

    # Get complete path to a stored file from its filename by
    # adding folder name
    @staticmethod
    def getFilePath(filename: str):
        return os.path.join(CoreConfig().get_temporary_directory(), filename)

    # Create stored file name by inserting current UTC date
    # and time into the pattern spot designated with "{0}"
    @staticmethod
    def makeFileName(pattern: str = '{0}', frequency: int = 0):
        d = datetime.utcnow().strftime('%y%m%d-%H%M%S')
        f = ('-%d' % (frequency // 1000)) if frequency>0 else ''
        return pattern.format(d + f)

    # Convert given file from BMP to PNG format using ImageMagick
    @staticmethod
    def convertImage(inFile: str):
        pm    = Config.get()
        compress = pm["image_compress"] # boolean. Do compression?
        compress_level = pm["image_compress_level"] # int 0-9. compression-level in magick
        compress_filter = pm["image_compress_filter"] # int 0-5. compression-filter in magick
        quantize = pm["image_quantize"] # boolean. Do quantization?
        quantize_colors = pm["image_quantize_colors"] # int. Number of colors in palette.
        
        # Adds storage path
        if not inFile.startswith('/'):
            inFile = self.getFilePath(inFile)
        # Only converting BMP files for now
        outFile = re.sub(r'\.bmp$', '.png', inFile)
        if outFile==inFile:
            return
        try:
            # Use ImageMagick to convert file
            params = ['convert', inFile]

            # Apply quantization if enabled
            if quantize:
                params.extend(["-colors", quantize_colors])

            # Apply compression options if enabled
            if compress:
                params.extend([
                    "-define", f"png:compression-level={compress_level}",
                    "-define", f"png:compression-filter={compress_filter}"
                ])

            # Final output file
            params.append(outFile)
            logger.debug("Converting image %s->%s: %s", inFile, outFile, ' '.join(params))
            subprocess.check_call(params)
            # If conversion was successful, delete original file
            os.unlink(inFile)
        except Exception as e:
            logger.debug("convertImage(): " + str(e))


class DataRecorder(object):
    def __init__(self, filePrefix: str = None, fileExtension: str = "", maxBytes: int = 8 * 1024 * 1024):
        self.frequency = 0
        self.filePfx   = filePrefix
        self.fileExt   = fileExtension
        self.file      = None
        self.maxBytes  = maxBytes
        self.cntBytes  = 0

    def __del__(self):
        # Close currently open file, if any
        self.closeFile()

    def closeFile(self):
        if self.file is not None:
            try:
                logger.info("Closing file '%s'." % self.file.name)
                self.file.close()
                self.file = None
                # Delete excessive files from storage
                logger.info("Performing storage cleanup...")
                Storage.getSharedInstance().cleanStoredFiles()
            except Exception as e:
                logger.error("Exception closing file: %s" % str(e))
                self.file = None

    def newFile(self, fileName):
        self.closeFile()
        try:
            logger.info("Opening file '%s'..." % fileName)
            self.file = Storage.getSharedInstance().newFile(fileName, buffering = 0)
            self.cntBytes = 0
        except Exception as e:
            logger.error("Exception opening file: %s" % str(e))
            self.file = None

    def writeFile(self, data):
        # If no file open, create and open a new file
        if self.file is None and self.filePfx is not None:
            self.newFile(Storage.makeFileName(self.filePfx+"-{0}", self.frequency) + self.fileExt)
        # If file open now...
        if self.file is not None:
            # Write new line into the file
            try:
                self.file.write(data)
            except Exception as e:
                logger.error("Exception writing file: %s" % str(e))
            # No more than maxBytes per file
            self.cntBytes = self.cntBytes + len(data)
            if self.cntBytes >= self.maxBytes:
                self.closeFile()

    def closeImage(self, newHeight: int, height: int, minHeight: int = 64):
        if self.file is not None:
            filePath = self.file.name
            # Update image height in the BMP file
            if newHeight != height:
                try:
                    fileSize = self.file.tell()
                    logger.debug("Updating '%s' height from %d to %d lines, %d bytes." % (filePath, height, newHeight, fileSize))
                    # File size
                    self.file.seek(2, 0)
                    self.writeFile((fileSize).to_bytes(4, "little"))
                    # File height
                    self.file.seek(22, 0)
                    self.writeFile((-newHeight & 0xFFFFFFFF).to_bytes(4, "little"))
                    # Back to the end
                    self.file.seek(0, 2)
                except Exception as e:
                    logger.debug("Exception updating image height: " + str(e))
            # Close file
            self.closeFile()
            if newHeight < minHeight:
                # Delete images that are too short
                logger.debug("Deleting '%s', shorter than %d lines..." % (filePath, minHeight))
                os.unlink(filePath)
            else:
                # Convert image from BMP to PNG
                logger.debug("Converting '%s' to PNG..." % filePath)
                Storage.convertImage(filePath)

    def setDialFrequency(self, frequency: int) -> None:
        # Open a new file if frequency changes
        if frequency != self.frequency:
            self.frequency = frequency
            self.closeFile()
