import configparser
import json
import logging
import os
import sys
import time

import flickrapi
from flickrapi.exceptions import FlickrError


logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.ini'


class Downloader(object):


    def __init__(self):
        self._load_config(CONFIG_FILE)

        self.api = flickrapi.FlickrAPI(self.api_key, self.api_secret,
                                        format='parsed-json')

        # To keep track of where we are during fetching.
        self.page_number = 1
        self.total_pages = 1

        # How many photos to get per page (500 is maximum).
        self.per_page = 5

        # Will store the IDs of all the photos to download.
        self.photo_ids = []

        # Will store the complete data about photos downloaded.
        self.results = []

        # Where we'll make directories and save the data and photos.
        self.path = os.getcwd()

    def _load_config(self, config_file):
        config = configparser.ConfigParser()

        try:
            config.read_file(open(config_file))
        except IOError:
            logger.critical("Can't read config file: " + config_file)
            exit()

        self.api_key = config.get('Flickr API', 'Key')
        self.api_secret = config.get('Flickr API', 'Secret')

    def authorize(self):
        """
        Get the OAuth token.
        """
        # Only do this if we don't have a valid token already
        if not self.api.token_valid(perms='read'):

            # Get a request token
            self.api.get_request_token(oauth_callback='oob')

            # Open a browser at the authentication URL. Do this however
            # you want, as long as the user visits that URL.
            authorize_url = self.api.auth_url(perms='read')

            logger.info("Open this URL in your web browser and, once you've signed in, and have agreed to authorization, you should get a code to type in:")
            logger.info(authorize_url)

            # Get the verifier code from the user. Do this however you
            # want, as long as the user gives the application the code.
            verifier = input('Verifier code: ')

            # Trade the request token for an access token
            self.api.get_access_token(verifier)

            logger.info("Done!")

        else:
            logger.info("This account is already authorised.")

    def download(self):
        """
        Fetch all the favorites - photos and data.
        """
        self._make_directories()

        self._fetch_user_info()

        self._fetch_pages()

        self._fetch_extra_data()

        self._save_results()

        logger.info("Done! Downloaded {} photo(s) and data".format(
                                                            len(self.results)))

    def _make_directories(self):
        """
        Makes the directories we'll save stuff to.
        """
        if os.path.exists( os.path.join(self.path, 'favorites') ):
            logger.critical("The 'favorites' directory already exists. Move or delete it before running this script.")
            exit()

        os.makedirs( os.path.join(self.path, 'favorites', 'data') )
        os.makedirs( os.path.join(self.path, 'favorites', 'photos') )

    def _fetch_user_info(self):
        """
        Calls test.login() to get the very basic user info for the
        authenticating user.
        Sets self.nsid with the Flickr User ID.
        Docs: https://www.flickr.com/services/api/flickr.test.login.htm
        """
        try:
            result = self.api.test.login()
        except FlickrError as e:
            logger.critical("Can't fetch Flickr user data: {}".format(e))
            exit()
        else:
            self.nsid = result['user']['id']

    def _fetch_pages(self):
        """
        Go through all the pages of photos and fetch the full list of photos.
        Just the basic data.
        """
        while self.page_number <= 1:
            self._fetch_page()
            self.page_number += 1
            time.sleep(0.5) # Being nice.

    def _fetch_page(self):
        """
        Fetch one page of basic data about some photos.
        Adds the fetched data to self.results.
        """
        try:
            photos = self.api.favorites.getList(
                                            user_id=self.nsid,
                                            per_page=self.per_page,
                                            page=self.page_number)
        except FlickrError as e:
            logger.critical(
                "Error when fetching recent photos (page {}): {}".format(
                                                        self.page_number, e))
            exit()
        else:
            if self.page_number == 1 and 'photos' in photos and 'pages' in photos['photos']:
                # First time, set the total_pages there are to fetch.
                self.total_pages = int(photos['photos']['pages'])

            # Just save the photo IDs. All we need for now.
            for photo in photos['photos']['photo']:
                self.photo_ids.append(photo['id'])

            logger.info(
                "Fetched one page of basic data about {} photo(s)".format(
                                            len(photos['photos']['photo'])))

    def _fetch_extra_data(self):
        """
        Now we've got the IDs of the photos, we go through and fetch
        complete data about each one and put it all into self.results.
        """
        for id in self.photo_ids:
            self.results.append({
                'info': self._fetch_photo_info(id),
                'sizes': self._fetch_photo_sizes(id),
                'exif': self._fetch_photo_exif(id),
            })

    def _fetch_photo_info(self, photo_id):
        """
        Calls the photos.getInfo() method of the Flickr API and returns the
        info about the photo.
        https://www.flickr.com/services/api/explore/flickr.photos.getInfo
        photo_id -- The Flickr photo ID.
        Returns a dict of data or None if something went wrong.
        """
        try:
            results = self.api.photos.getInfo(photo_id = photo_id)
            results = results['photo']
        except FlickrError as e:
            logger.error("Couldn't fetch photo info for {}: {}".format(
                                                                photo_id, e))
            results = None

        return results

    def _fetch_photo_sizes(self, photo_id):
        """Calls the photos.getSizes() method of the Flickr API and returns the
        photo's sizes.
        https://www.flickr.com/services/api/explore/flickr.photos.getSizes
        photo_id -- The Flickr photo ID.
        Returns a dict of data or None if something went wrong.
        """
        try:
            results = self.api.photos.getSizes(photo_id = photo_id)
            results = results['sizes']
        except FlickrError as e:
            logger.error("Couldn't fetch photo sizes for {}: {}".format(
                                                                photo_id, e))
            results = None

        return results

    def _fetch_photo_exif(self, photo_id):
        """Calls the photos.getExif() method of the Flickr API and returns the
        photo's EXIF data.
        https://www.flickr.com/services/api/explore/flickr.photos.getExif
        photo_id -- The Flickr photo ID.
        Returns a dict of data or None if something went wrong.
        """
        try:
            results = self.api.photos.getExif(photo_id = photo_id)
            results = results['photo']
        except FlickrError as e:
            logger.error("Couldn't fetch photo EXIF data for {}: {}".format(
                                                                photo_id, e))
            results = None

        return results

    def _save_results(self):
        """
        Having got all the data in self.results, save it to JSON files.
        """
        # for photo in self.results:
        for photo_data in self.results:
            base_filename = self._make_filename(photo_data)
            base_path = os.path.join(self.path, 'favorites', 'data')

            for kind in ['info', 'exif', 'sizes']:
                if photo_data[kind] is not None:
                    filename = '{}_{}.json'.format(base_filename, kind)

                    path = os.path.join(base_path, filename)

                    with open(path, 'w') as f:
                        f.write( json.dumps(photo_data[kind], indent=2) )

    def _make_filename(self, photo_data):
        """
        Makes a filename for this photo using the date, owner and ID.
        Does not include the file extension.
        """
        if photo_data['info']['owner']['realname'] != '':
            name = photo_data['info']['owner']['realname']
        else:
            name = photo_data['info']['owner']['username']

        filename = '{}_{}_{}'.format(
                                photo_data['info']['dates']['taken'],
                                name,
                                photo_data['info']['id'])

        filename = filename.replace(' ', '_') \
                            .replace('/', '-') \
                            .replace(':', '-') \

        keep_chars = ('-', '_')

        filename = "".join(
                        c for c in filename if c.isalnum() or c in keep_chars)

        return filename



if __name__ == "__main__":

    downloader = Downloader()

    action = sys.argv[-1]

    if action == 'authorize':
        downloader.authorize()
    else:
        downloader.download()
