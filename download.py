import configparser
import json
import logging
import os
import re
import shutil
import sys
import time

import flickrapi
from flickrapi.exceptions import FlickrError
import requests


logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.ini'


class Downloader(object):

    def __init__(self):
        self._load_config(CONFIG_FILE)

        self.api = flickrapi.FlickrAPI(self.api_key, self.api_secret,
                                        format='parsed-json')

        # Will be 'favorites' or 'photos_of_me'.
        self.kind = None

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

    def get_favorites(self):
        """
        Fetch and save all the favorites - photos and data.
        """
        self.kind = 'favorites'

        logging.info("Fetching favorites")

        self._start_fetching()

    def get_photos_of_me(self):
        """
        Fetch and save all the photos of the user - photos and data.
        """
        self.kind = 'photos_of_me'

        logging.info("Fetching 'photos of me'")

        self._start_fetching()

    def _start_fetching(self):
        """
        Starts the entire process, once self.kind has been set.
        """
        self._make_directories()

        self._fetch_user_info()

        self._fetch_pages()

        self._fetch_extra_data()

        self._save_results()

        self._fetch_photos()

        self._make_html_file()

        logger.info("Done! Downloaded {} photo(s) and data".format(
                                                            len(self.results)))

    def _make_directories(self):
        """
        Makes the directories we'll save stuff to.
        """
        if os.path.exists( os.path.join(self.path, self.kind) ):
            logger.critical("The '{}' directory already exists. Move or delete it before running this script.".format(self.kind))
            exit()

        os.makedirs( os.path.join(self.path, self.kind, 'data') )
        os.makedirs( os.path.join(self.path, self.kind, 'photos') )

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
        time.sleep(0.5) # Being nice.

        try:
            if self.kind == 'photos_of_me':
                photos = self.api.people.getPhotosOf(
                                            user_id='me',
                                            per_page=self.per_page,
                                            page=self.page_number)
            else:
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
        for photo in self.results:
            base_filename = self._make_filename(photo['info'])
            base_path = os.path.join(self.path, self.kind, 'data')

            for kind in ['info', 'exif', 'sizes']:
                if photo[kind] is not None:
                    filename = '{}_{}.json'.format(base_filename, kind)

                    path = os.path.join(base_path, filename)

                    with open(path, 'w') as f:
                        f.write( json.dumps(photo[kind], indent=2) )

    def _fetch_photos(self):
        """
        Once we've got all the data, download the actual photo/video files and
        save them.
        We try to save the original files if possible.
        """
        for photo in self.results:
            if photo['sizes'] is not None:
                if photo['info']['media'] == 'video':
                    # Accepted video formats:
                    # https://help.yahoo.com/kb/flickr/sln15628.html
                    # BUT, they all seem to be sent as video/mp4.
                    content_types = ['video/mp4',]
                    url = self._get_url_from_sizes(photo['sizes'], 'Site MP4')
                else:
                    content_types = [
                        'image/jpeg', 'image/jpg', 'image/png', 'image/gif',]
                    if 'originalformat' in photo['info']:
                        url = self._get_url_from_sizes(photo['sizes'], 'Original')
                    else:
                        # Can't download the original file so:
                        url = self._get_url_from_sizes(photo['sizes'], 'Large 2048')

                if url is None:
                    logger.error(
                        "Couldn't find the URL to download for photo {}".format(
                                                        photo['info']['id']))

                download_filepath = self._download_file(url, content_types)

                if download_filepath is not None:
                    save_filepath = self._make_photo_filepath(photo['info'])
                    os.rename(download_filepath, save_filepath)

    def _make_filename(self, photo_info):
        """
        Makes a filename for this photo or its data using its date, owner and ID.
        Does not include the file extension.
        Used for making the JSON files' names as well as the photo/video itself.
        """
        if photo_info['owner']['realname'] != '':
            name = photo_info['owner']['realname']
        else:
            name = photo_info['owner']['username']

        filename = '{}_{}_{}'.format(
                                photo_info['dates']['taken'],
                                name,
                                photo_info['id'])

        filename = filename.replace(' ', '_') \
                            .replace('/', '-') \
                            .replace(':', '-') \

        keep_chars = ('-', '_')

        filename = "".join(
                        c for c in filename if c.isalnum() or c in keep_chars)

        return filename

    def _make_photo_filename(self, photo_info):
        """
        Makes the filename for the photo we'll save to disk, including extension.
        """
        if photo_info['media'] == 'video':
            extension = 'mp4'
        else:
            if 'originalformat' in photo_info:
                extension = photo_info['originalformat']
            else:
                # Can't download the original file so:
                extension = 'jpg'

        base_filename = self._make_filename(photo_info)
        filename = '{}.{}'.format(base_filename, extension)

        return filename

    def _make_photo_filepath(self, photo_info):
        """
        Makes the coplete path for the photo we'll save to disk.
        """
        filename = self._make_photo_filename(photo_info)
        return  os.path.join(self.path, self.kind, 'photos', filename)

    def _get_url_from_sizes(self, sizes, size):
        """
        Given the dict of 'sizes' data for a phoot/video, return the URL
        referred to by `size` (e.g. 'Original', 'Medium 640', etc).
        """
        for url in sizes['size']:
            if url['label'] == size:
                return url['source']

        # Shouldn't get here, but...
        return None

    def _download_file(self, url, acceptable_content_types):
        """
        Downloads a file from a URL and saves it into /tmp/.
        Returns the filepath of the downlaoded file, or None if something goes
        wrong.

        Expects:
            url -- The URL of the file to fetch.
            acceptable_content_types -- A list of MIME types the request must
                match. eg:['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
        """
        logger.info("Downloading {}".format(url))

        try:
            # From http://stackoverflow.com/a/13137873/250962
            r = requests.get(url, stream=True)
            if r.status_code == 200:
                try:
                    if r.headers['Content-Type'] in acceptable_content_types:
                        # Where we'll temporarily save the file:
                        filename = self._get_downloaded_filename(url, r.headers)
                        filepath = '%s%s' % (self.path, filename)
                        # Save the file there:
                        with open(filepath, 'wb') as f:
                            r.raw.decode_content = True
                            shutil.copyfileobj(r.raw, f)
                        return filepath
                    else:
                        logger.log('error',
                        "Invalid content type ({}) when fetching {}".format(
                                            r.headers['content_type'], url))
                except KeyError:
                    logger.log('error',
                        "No content_type headers found when fetching {}".format(url))
            else:
                logger.log('error',
                                "Got status code {} when fetching {}".format(
                                                        r.status_code, url))
        except requests.exceptions.RequestException as e:
            logger.log('error',
                        "Something when wrong when fetching {}: {}".format(url, e))

        # Something went wrong if we end up here.
        return None

    def _get_downloaded_filename(self, url, headers={}):
        """
        Find the filename of a downloaded file.
        Returns a string.

        url -- The URL of the file that's been downloaded.
        headers -- A dict of response headers from requesting the URL.

        url will probably end in something like 'filename.jpg'.
        If not, we'll try and use the filename from the Content-Disposition
        header.
        This is the case for Videos we download from Flickr.
        """
        # Should work for photos:
        filename = os.path.basename(url)

        if filename == '':
            # Probably a Flickr video, so we have to get the filename from
            # headers:
            try:
                # Could be like 'attachment; filename=26897200312.avi'
                disposition = headers['Content-Disposition']
                m = re.search(
                            'filename\=(.*?)$', headers['Content-Disposition'])
                try:
                    filename = m.group(1)
                except (AttributeError, IndexError):
                    pass
            except KeyError:
                pass

        return filename

    def _make_html_file(self):
        """
        Write a single HTML file listing all the photos.
        I know this is ugly and a template would be better.
        """
        list_html = ''

        for photo in self.results:
            if photo['info']['owner']['realname']:
                name = photo['info']['owner']['realname']
            else:
                name = photo['info']['owner']['username']

            file = os.path.join('')

            flickr_url = ''
            for u in photo['info']['urls']['url']:
                if u['type'] == 'photopage':
                    flickr_url = u['_content']

            description = ''
            if photo['info']['description']['_content'] != '':
                description = '<p>{}</p>'.format(
                                    photo['info']['description']['_content'])

            data = {
                'title': photo['info']['title']['_content'],
                'author': name,
                'file': self._make_photo_filepath(photo['info']),
                'description': description,
                'date_taken': photo['info']['dates']['taken'],
                'flickr_url': flickr_url,
            }
            list_html += """
<h2>{title}</h2>
<ul>
    <li>By {author}</li>
    <li>Taken {date_taken}</li>
    <li><a href="{file}">Downloaded file</a> | <a href="{flickr_url}">On Flickr</a><li>
</ul>
{description}
""".format(
                title=data['title'],
                author=data['author'],
                date_taken=data['date_taken'],
                file=data['file'],
                flickr_url=data['flickr_url'],
                description=data['description'],
            )

            if self.kind == 'favorites':
                title = 'Favorites'
            else:
                title = 'Photos of you'

            css = """
    body { background: #fff; color: #000; font-family: Helvetica, Arial, sans-serif; line-height: 1.5; padding: 0 30px 2em 30px; }
    h2 { margin: 1em 0 0 0; }
    ul { list-style-type: none; margin: 0; padding: 0; }
"""

            html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style type="text/css">
    {css}
  </style>
</head>
<body>
    <h1>{title}</h1>

    {list_html}
</body>
</html>""".format(
                title=title,
                css=css,
                list_html=list_html,
            )

        path = os.path.join(self.path, self.kind, 'index.html')

        with open(path, 'w') as f:
            f.write(html)

if __name__ == "__main__":

    downloader = Downloader()

    action = sys.argv[-1]

    if action == 'authorize':
        downloader.authorize()
    elif action == 'favorites':
        downloader.get_favorites()
    elif action == 'photosofme':
        downloader.get_photos_of_me()
    else:
        logger.critical("Specify one of 'authorize', 'favorites' or 'photosof'.")
