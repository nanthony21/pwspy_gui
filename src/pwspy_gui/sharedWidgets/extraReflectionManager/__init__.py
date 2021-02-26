# Copyright 2018-2020 Nick Anthony, Backman Biophotonics Lab, Northwestern University
#
# This file is part of PWSpy.
#
# PWSpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PWSpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PWSpy.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

import logging
import os
import typing
from io import IOBase
from typing import Optional, Dict, List
import pickle

from PyQt5 import QtCore
from PyQt5.QtCore import QObject, QThread
from PyQt5.QtWidgets import QMessageBox, QWidget

import httplib2
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.auth.exceptions import TransportError

from pwspy.dataTypes import ERMetaData
from pwspy_gui.PWSAnalysisApp import applicationVars
from pwspy_gui.sharedWidgets.dialogs import BusyDialog
from pwspy_gui.sharedWidgets.extraReflectionManager.ERDataComparator import ERDataComparator
from pwspy_gui.sharedWidgets.extraReflectionManager._ERDataDirectory import ERDataDirectory, EROnlineDirectory
from ._ERSelectorWindow import ERSelectorWindow
from ._ERUploaderWindow import ERUploaderWindow
from .exceptions import OfflineError

if typing.TYPE_CHECKING:
    from google.oauth2.credentials import Credentials


def _offlineDecorator(func):
    """Functions decorated with this will raise an OfflineError if they are attempted to be called while the ERManager
    is in offline mode. Only works on instance methods."""
    def wrappedFunc(self, *args, **kwargs):
        if self.offlineMode:
            logging.getLogger(__name__).warning("Attempting to download when ERManager is in offline mode.")
            raise OfflineError("Is Offline")
        func(self, *args, **kwargs)
    return wrappedFunc


class ERManager:
    """This class expects that the google drive application will already have access to a folder named
    `PWSAnalysisAppHostedFiles` which contains a folder `ExtraReflectanceCubes`, you will
    have to create these manually if starting on a new Drive account.

    Args:
        filePath: The file path to the local folder where Extra Reflection calibration files are stored.
        parentWidget: An optional reference to a QT widget that will act as the parent to any dialog windows that are opened.
    """
    def __init__(self, filePath: str, parentWidget: QWidget = None):
        self._directory = filePath
        self.offlineMode, self._downloader = self._logIn(parentWidget)

        indexPath = os.path.join(self._directory, 'index.json')
        if not os.path.exists(indexPath) and not self.offlineMode:
            self.download('index.json')
        self.dataComparator = ERDataComparator(self._downloader, self._directory)

    def _logIn(self, parentWidget: QWidget) -> typing.Tuple[bool, ERDownloader]:
        logger = logging.getLogger(__name__)
        logger.debug("Calling ERDownloader.getCredentials")
        creds = ERDownloader.getCredentials(applicationVars.googleDriveAuthPath)
        logger.debug("Finished ERDownloader.getCredentials")
        if creds is None:  # Check if the google drive credentials exists and if they don't then give the user a message.
            msg = QMessageBox(parentWidget)
            msg.setIcon(QMessageBox.Information)
            msg.setText("Please log in to the google drive account containing the PWS Calibration Database. This is currently backman.lab@gmail.com")
            msg.setWindowTitle("Time to log in!")
            msg.setWindowModality(QtCore.Qt.WindowModal)
            okButton = msg.addButton("Ok", QMessageBox.YesRole)
            skipButton = msg.addButton("Skip (offline mode)", QMessageBox.NoRole)
            msg.exec()
            if msg.clickedButton() is skipButton:
                return True, None
        try:
            downloader = ERDownloader(applicationVars.googleDriveAuthPath)
            return False, downloader
        except (TransportError, httplib2.ServerNotFoundError):
            msg = QMessageBox.information(parentWidget, "Internet?", "Google Drive connection failed. Proceeding in offline mode.")
            return True, None

    def createSelectorWindow(self, parent: QWidget):
        return ERSelectorWindow(self, parent)

    def createManagerWindow(self, parent: QWidget):
        return ERUploaderWindow(self, parent)

    @_offlineDecorator
    def download(self, fileName: str, parentWidget: Optional[QWidget] = None):
        """Begin downloading `fileName` in a separate thread. Use the main thread to update a progress bar.
        If directory is left blank then file will be downloaded to the ERManager main directory"""
        self._downloader.download(fileName, self._directory, parentWidget)

    @_offlineDecorator
    def upload(self, fileName: str):
        """Uploads the file at `fileName` to the `ExtraReflectanceCubes` folder of the google drive account"""
        filePath = os.path.join(self._directory, fileName)
        self._downloader.upload(filePath)

    def getMetadataFromId(self, idTag: str) -> ERMetaData:
        """Given the unique idTag string for an ExtraReflectanceCube this will search the index.json and return the
        ERMetaData file. If it cannot be found then an `IndexError will be raised."""
        try:
            match = [item for item in self.dataComparator.local.index.cubes if item.idTag == idTag][0]
        except IndexError:
            raise IndexError(f"An ExtraReflectanceCube with idTag {idTag} was not found in the index.json file at {self._directory}.")
        return ERMetaData.fromHdfFile(self._directory, match.name)


class ERDownloader:
    """Implements downloading functionality specific to the structure that we have calibration files stored on our google drive account."""
    def __init__(self, authPath: str):
        self._downloader = _QtGoogleDriveDownloader(authPath)

    def download(self, fileName: str, directory: str, parentWidget: Optional[QWidget] = None):
        """Begin downloading `fileName` in a separate thread. Use the main thread to update a progress bar.
        If directory is left blank then file will be downloaded to the ERManager main directory"""
        t = self._DownloadThread(self._downloader, fileName, directory)
        b = BusyDialog(parentWidget, f"Downloading {fileName}. Please Wait...", progressBar=True)  # This dialog blocks the screen until the download thread is completed.
        t.finished.connect(b.accept)  # When the thread finishes, close the busy dialog.
        self._downloader.progress.connect(b.setProgress)  # Progress from the downloader updates a progress bar on the busy dialog.
        t.errorOccurred.connect(lambda e: QMessageBox.information(parentWidget, 'Error in Drive Downloader Thread', str(e)))
        t.start()
        b.exec()

    def downloadToRam(self, fileName: str, stream: IOBase) -> IOBase:
        """Download a file directly to a stream in ram rather than saving to file, best for small temporary files.
        Args:
            fileName (str): The name of the file stored on google drive, must be in the Extra reflectance directory.
            stream (IOBase): An empty stream that the file contents will be loaded into.
        Returns:
            IOBase: The same stream that was passed in as `stream`."""
        files = self._downloader.getFolderIdContents(
            self._downloader.getIdByName('PWSAnalysisAppHostedFiles'))
        files = self._downloader.getFolderIdContents(
            self._downloader.getIdByName('ExtraReflectanceCubes', fileList=files))
        fileId = self._downloader.getIdByName(fileName, fileList=files)  
        self._downloader.downloadFile(fileId, stream)
        return stream

    def upload(self, filePath: str):
        parentId = self._downloader.getIdByName("ExtraReflectanceCubes")
        self._downloader.uploadFile(filePath, parentId)

    def getFileMetadata(self) -> List[Dict]:
        """Return GoogleDrive metadata about the files in the extra reflectance drive folder"""
        files = self._downloader.getFolderIdContents(
            self._downloader.getIdByName('PWSAnalysisAppHostedFiles'))
        files = self._downloader.getFolderIdContents(
            self._downloader.getIdByName('ExtraReflectanceCubes', fileList=files))
        return files

    @staticmethod
    def getCredentials(authPath: str):
        return GoogleDriveDownloader.getCredentials(authPath)

    class _DownloadThread(QThread):
        """A QThread to download from google drive"""
        errorOccurred = QtCore.pyqtSignal(Exception)  # If an exception occurs it can be passed to another thread with this signal

        def __init__(self, downloader: GoogleDriveDownloader, fileName: str, directory: str):
            super().__init__()
            self.downloader = downloader
            self.fileName = fileName
            self.directory = directory

        def run(self):
            try:
                files = self.downloader.getFolderIdContents(
                    self.downloader.getIdByName('PWSAnalysisAppHostedFiles'))
                files = self.downloader.getFolderIdContents(
                    self.downloader.getIdByName('ExtraReflectanceCubes', fileList=files))
                fileId = self.downloader.getIdByName(self.fileName, fileList=files)
                with open(os.path.join(self.directory, self.fileName), 'wb') as f:
                    self.downloader.downloadFile(fileId, f)
            except Exception as e:
                self.errorOccurred.emit(e)


class GoogleDriveDownloader:
    """Handles downloading and uploading files from Google Drive.

    Upon initializing an instance of this class you will be asked for username and password if you don't already have
    authentication saved from a previous login.

    Args:
        authPath: The folder to store authentication files. Before this class will work you will need to place
            `credentials.json` in the authPath. You can get this file from the online Google Drive api console. Create
            an Oauth 2.0 credential with access to the `drive.file` api.

."""
    def __init__(self, authPath: str):
        self._allFiles = None  #A list of all the files that we have access to. updated by self._updateFilesList()
        self._authPath = authPath
        tokenPath = os.path.join(self._authPath, 'driveToken.pickle')
        credPath = os.path.join(self._authPath, 'credentials.json')
        creds = self.getCredentials(self._authPath)
        if not creds or not creds.valid:  # If there are no (valid) credentials available, let the user log in.
            if creds and creds.expired and creds.refresh_token:  # Attempt to refresh the credentials.
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credPath, ['https://www.googleapis.com/auth/drive.file'])
                creds = flow.run_local_server(port=8090)  # Opens the google login window in a browser.
            with open(tokenPath, 'wb') as token:  # Save the credentials for the next run
                pickle.dump(creds, token)
        self.api = build('drive', 'v3', credentials=creds)  # this returns access to the drive api. see google documentation. All drive related functionality happens through this api.
        self._updateFilesList()

    @staticmethod
    def getCredentials(authPath: str) -> Credentials:
        """
        Args:
            authPath: The folder path to the authentication folder.

        Returns:
             The Google Drive credentials stored in `driveToken.pickle`
        """
        tokenPath = os.path.join(authPath, 'driveToken.pickle')
        creds = None
        if os.path.exists(tokenPath):
            with open(tokenPath, 'rb') as token:
                creds = pickle.load(token)
        return creds

    def _updateFilesList(self):
        """Update the list of all files in the Google Drive account. This is automatically called during initialization
         and after uploading a new file. I don't think it should be needed anywhere else."""
        results = self.api.files().list(fields="nextPageToken, files(id, name, parents, md5Checksum)").execute()
        self._allFiles = results.get('files', [])

    def getIdByName(self, name: str, fileList: Optional[List] = None) -> str:
        """Return the file id associated with a filename.

        Args:
            name: The filename you want the ID for.
            fileList: A list of metadata such as is returned by getFolderIDContents. if left as `None` then all files
            are searched. If there are multiple files with the same name the first match that is found will be returned.

        Returns:
            The ID string of the file.
        """
        if fileList is None:
            fileList = self._allFiles
        matches = [i['id'] for i in fileList if i['name'] == name]
        if len(matches) > 1:
            raise ValueError(f"Google Drive found multiple files matching file name: {name}")
        elif len(matches) == 0:
            raise ValueError(f"Google Drive found not files matching file name: {name}")
        else:
            return matches[0]

    def getFolderIdContents(self, Id: str) -> List[Dict]:
        """Return the API metadata for all files contained within the folder associated with `id`.

        Args:
            Id: the file ID as returned by `getIdByName`.

        Returns:
            A list of file metadata.
        """
        files = [i for i in self._allFiles if 'parents' in i] # Get rid of parentless files. they will cause errors.
        return [i for i in files if Id in i['parents']]

    def downloadFile(self, Id: str, file: IOBase):
        """Save the file with `id` as it Google Drive ID

        Args:
            Id: the file ID as returned by `getIdByName`.
            file: A file or other stream to save to.
        """
        fileRequest = self.api.files().get_media(fileId=Id)
        downloader = MediaIoBaseDownload(file, fileRequest)
        done = False
        logger = logging.getLogger(__name__)
        while done is False:
            status, done = downloader.next_chunk()
            logger.info("Download %d%%." % int(status.progress() * 100))

    def createFolder(self, name: str, parentId: Optional[str] = None) -> str:
        """Creates a folder with name `name` and returns the id number of the folder
        If parentId is provided then the folder will be created inside the parent folder.

        Args:
            name: The name of the new folder
            parentId: The ID of the folder you want to create this folder inside of.

        Returns:
            The ID of the new folder
        """
        folderMetadata = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
        if parentId: folderMetadata['parents'] = [parentId]
        folder = self.api.files().create(body=folderMetadata, fields='id').execute()
        return folder.get('id')

    def uploadFile(self, filePath: str, parentId: str) -> str:
        """Upload the file at `filePath` to the folder with `parentId`, keeping the original file name.
        If a file with the same parent and name already exists, replace it.

        Args:
            filePath: the local path the file that should be uploaded
            parentId: The ID of the folder that the file should be uploaded to.

        Returns:
            The ID of the newly uploaded file.

        """
        fileName = os.path.split(filePath)[-1]
        existingFiles = self.getFolderIdContents(parentId)
        if fileName in [i['name'] for i in existingFiles]: #FileName already exists
            existingId = [i['id'] for i in existingFiles if i['name'] == fileName][0]
            self.api.files().delete(fileId=existingId).execute()
        fileMetadata = {'name': fileName, 'parents': [parentId]}
        media = MediaFileUpload(filePath)
        file = self.api.files().create(body=fileMetadata, media_body=media, fields='id').execute()
        self._updateFilesList()
        return file.get('id')

    def moveFile(self, fileId: str, newFolderId: str):
        """Move a file that is already uploaded to Google Drive.

        Args:
            fileId: the ID of the file that should be moved.
            newFolderId: The ID of the parent folder you want to move the file to.

        """
        file = self.api.files().get(fileId=fileId, fields='parents').execute()
        oldParents = ','.join(file.get('parents'))
        file = self.api.files().update(fileId=fileId, addParents=newFolderId, removeParents=oldParents, fields='id, parents').execute()


class _QtGoogleDriveDownloader(GoogleDriveDownloader, QObject):
    """Same as the standard google drive downloader except it emits a progress signal after each chunk downloaded. This can be used to update a progress bar."""
    progress = QtCore.pyqtSignal(int)  # gives an estimate of download progress percentage

    def __init__(self, authPath: str):
        GoogleDriveDownloader.__init__(self, authPath)
        QObject.__init__(self)

    def downloadFile(self, Id: str, file: IOBase):
        """Save the file with googledrive file identifier `Id` to `savePath` while emitting the `progress` signal
        which can be connected to a progress bar or whatever."""
        fileRequest = self.api.files().get_media(fileId=Id)
        downloader = MediaIoBaseDownload(file, fileRequest, chunksize=1024*1024*5) # Downloading in 5mb chunks instead of the default 100mb chunk just so that the progress bar looks smoother
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            self.progress.emit(int(status.progress() * 100))
