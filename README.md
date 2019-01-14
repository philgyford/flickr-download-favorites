# Flickr Download Favorites

A python script that:

* Downloads all your 'Fave' photos and videos from Flickr
* Saves JSON files of data about each one
* Makes a basic HTML file listing all the downloads
* Can do the same for 'Photos of You'


## Installation

1. Download or check out this code.

2. Install the dependencies with pip:

        pip install -r requirements.txt

    or with pipenv:

        pipenv install

3. Create an App for the Flickr API at https://www.flickr.com/services/apps/create/apply/

4. Copy the `config_example.ini` file to `config.ini`.

5. Replace the values in `config.ini` with your App's API Key and API Secret.


## Usage

Before fetching anything you'll need to get the OAuth token by running this:

    python download.py authorize

and following the instructions it gives you.

Once that's done, download your Faves by doing:

    python download.py favorites

And download Photos Of You by doing:

    python download.py photosof

If you run these again in the future, only new photos/videos will be downloaded,
assuming your directories of photos and data are still in place from previous
runs. If previously-downloaded photos have been deleted on Flickr, or if you've
un-faved them, they won't be deleted from your local copy.


## Results

Assuming all goes well each command creates on directory (`favorites/` or
`photosof/`).

Inside each one will be:

    * `photos/` - All the downloaded photos and videos.

      Where possible the original photos will be downloaded, otherwise the
      largest size available.

      Videos are downloaded as MP4 files.

      All filenames are of the format `datetime_name_id.ext`, e.g.
      `2018-12-24_11-58-20_Mary_Loosemore_46511930971.jpg`. The datetime is the
      time the photo was taken, and the name is the person whose photo it is.

    * `data/` - For every photo/video there should be 2 or 3 JSON files, with
      names similar to their associated photo/video.
        * `[filename]_exif.json` - The results of [`photo.getExif()`][exif]
        * `[filename]_info.json` - The results of [`photo.getInfo()`][info]
        * `[filename]_sizes.json` - The results of [`photo.getSizes()`][sizes]
      If there was an error fetching the data for a photo, or it's not
      available, that file will not be present.

     * `index.html` - A basic HTML file listing all the downloaded,
       photos/videos, some information about them, and links to the downloaded
       file and its page on Flickr.com.


## A note on privacy and rights

Remember that all these files are downloaded as if they were viewed on the site
by you, with your permissions. This means you can download photos/videos that
are only visible to you or a small number of people, so don't go sharing them
all without checking their permissions on the site (or in the JSON files) first.

Also, the licenses might be restrictive -- such as "All Rights Reserved" -- so
be aware of this too.

If the original is no longer on Flickr this information can be found in the
`*_info.json` file for the photo/video.

The data have a `visibility` attribute that indicates who it is visible for.
e.g. this photo is private, but visible to both Friends and Family:

```
  "visibility": {
    "ispublic": 0,
    "isfriend": 1,
    "isfamily": 1
  },
```

The data also have a `license` attribute that's a digit. This refers to the
licenses as returned by the [licenses.getInfo][licenses] command:

```
 0 All Rights Reserved
 1 Attribution-NonCommercial-ShareAlike License
 2 Attribution-NonCommercial License
 3 Attribution-NonCommercial-NoDerivs License
 4 Attribution License
 5 Attribution-ShareAlike License
 6 Attribution-NoDerivs License
 7 No known copyright restrictions
 8 United States Government Work
 9 Public Domain Dedication (CC0)
10 Public Domain Mark
```

[exif]: https://www.flickr.com/services/api/flickr.photos.getExif.htm
[info]: https://www.flickr.com/services/api/flickr.photos.getInfo.htm
[sizes]: https://www.flickr.com/services/api/flickr.photos.getSizes.htm
[licenses]: https://www.flickr.com/services/api/flickr.photos.licenses.getInfo.html
