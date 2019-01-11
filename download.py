import configparser
import datetime
import json
import logging
import os
import pytz
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

        self.page_number = 1
        self.total_pages = 1
        self.per_page = 5
        self.results = []

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
        Fetch all the favorites.
        """
        self._make_directories()

        self._fetch_user_info()

        self._fetch_pages()

        self._fetch_extra_data()

        self._save_results()

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
        Sets self.user_id with the Flickr User ID.
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
        while self.page_number <= 1:
            self._fetch_page()
            self.page_number += 1
            time.sleep(0.5) # Being nice.

    def _fetch_page(self):
        """
        Fetch one page of initial data about some photos.
        """
        try:
            results = self.api.favorites.getList(
                                            user_id=self.nsid,
                                            per_page=self.per_page,
                                            page=self.page_number)
        except FlickrError as e:
            logger.critical(
                "Error when fetching recent photos (page {}): {}".format(
                                                        self.page_number, e))
            exit()
        else:
            if self.page_number == 1 and 'photos' in results and 'pages' in results['photos']:
                # First time, set the total_pages there are to fetch.
                self.total_pages = int(results['photos']['pages'])

            # Add the list of photos' data from this page on to our total list:
            self.results += results['photos']['photo']

            logger.info("Fetched initial data about {} photo(s)".format(
                                            len(results['photos']['photo'])))

    def _fetch_extra_data(self):
        """
        Before saving we need to go through the big list of photos we've
        fetched, and fetch more detailed info to add to each photo's data.
        """
        extra_results = []

        for i, photo in enumerate(self.results):

            extra_results.append({
                'fetch_time': datetime.datetime.utcnow().replace(tzinfo=pytz.utc),
                # Get all the info about this photo:
                'info': self._fetch_photo_info(photo['id']),
                'sizes': self._fetch_photo_sizes(photo['id']),
                'exif': self._fetch_photo_exif(photo['id']),
            })

        # Replace self.results with our new array that contains more info.
        self.results = extra_results

    def _fetch_photo_info(self, photo_id):
        """
        Calls the photos.getInfo() method of the Flickr API and returns the
        info about the photo.
        https://www.flickr.com/services/api/explore/flickr.photos.getInfo
        photo_id -- The Flickr photo ID.
        """
        try:
            results = self.api.photos.getInfo(photo_id = photo_id)
        except FlickrError as e:
            logger.error("Couldn't fetch photo info for {}: {}".format(
                                                                photo_id, e))
            results = {'photo': {}}

        return results['photo']

    def _fetch_photo_sizes(self, photo_id):
        """Calls the photos.getSizes() method of the Flickr API and returns the
        photo's sizes.
        https://www.flickr.com/services/api/explore/flickr.photos.getSizes
        photo_id -- The Flickr photo ID.
        """
        try:
            results = self.api.photos.getSizes(photo_id = photo_id)
        except FlickrError as e:
            logger.error("Couldn't fetch photo sizes for {}: {}".format(
                                                                photo_id, e))
            results = {'sizes': {}}

        return results['sizes']

    def _fetch_photo_exif(self, photo_id):
        """Calls the photos.getExif() method of the Flickr API and returns the
        photo's EXIF data.
        https://www.flickr.com/services/api/explore/flickr.photos.getExif
        photo_id -- The Flickr photo ID.
        """
        try:
            results = self.api.photos.getExif(photo_id = photo_id)
        except FlickrError as e:
            logger.error("Couldn't fetch photo EXIF data for {}: {}".format(
                                                                photo_id, e))
            results = {'photo': {}}

        return results['photo']

    def _save_results(self):
        # for photo in self.results:
        for photo_data in self.results:
            base_filename = self._make_filename(photo_data)
            base_path = os.path.join(self.path, 'favorites', 'data')

            for kind in ['info', 'exif', 'sizes']:
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

        filename = filename.replace(' ', '_')

        return filename



if __name__ == "__main__":

    downloader = Downloader()

    action = sys.argv[-1]

    if action == 'authorize':
        downloader.authorize()
    else:
        downloader.download()
