#!/usr/bin/env python

"""Post a new tweet
"""

import os
import sys
import json
import argparse
import urllib
from poster.encode import multipart_encode
from unicodedata import normalize

import oauth2 as oauth
from ttp import ttp

with open("twitter_config.json") as _config_file:
    _config = json.load(_config_file)

def main():
    parser = argparse.ArgumentParser(description=__doc__.strip())
    args = parser.parse_args()

    # Get twitter configuration
    _, twitter_config = send_request("/help/configuration.json", "GET")

    # Wait for user to input a multiline tweet text
    print "New tweet (End tweet with an empty line):"
    sentinel = ""
    lines = []
    for line in iter(raw_input, sentinel):
        lines.append(line.decode(sys.stdin.encoding))
    # Join lines and normalize
    text = normalize("NFC", unicode('\n', "utf-8").join(lines))

    # Prompt for files to upload
    valid_media_format = ["png", "jpg", "jpeg", "gif"]
    max_media_files = twitter_config["max_media_per_upload"]
    media_input = raw_input(
        "Files to upload (Separate by spaces), %s maximum:\n" % max_media_files)
    uploads = []
    if media_input:
        medias = media_input.strip().split()
        if len(medias) > max_media_files:
            raise RuntimeError("Maximum number of files to upload %s" %
                               max_media_files)
        for media in medias:
            if os.path.splitext(media)[-1].strip(".") not in valid_media_format:
                raise RuntimeError("%s: Invalid file format. "
                "Format has to be %s" % (media, ", ".join(valid_media_format)))
            elif not os.path.exists(media):
                raise RuntimeError("%s: File doesn't exit" % media)
            elif os.path.getsize(media) > twitter_config["photo_size_limit"]:
                raise RuntimeError("%s: Exceed maximum file size %s" %
                        (media, h_size))
            else:
                uploads.append(media)

    # Calculate characters reserved for media
    media_character_len = len(uploads) * \
        twitter_config["characters_reserved_per_media"] + len(uploads)

    # Calculate difference between normal and warpped links
    # Tweet parser
    tweet_parser = ttp.Parser()
    result = tweet_parser.parse(text)
    url_length_difference = 0
    for url in result.urls:
        url_length_difference += len(url) - get_url_length(url, twitter_config)

    # Reject post over 140 characters
    text_length = len(text) - url_length_difference - media_character_len
    if text_length > 140:
        raise RuntimeError(
                "Tweets can't be over 140 characters. Your tweet has %s "
                "characters." % text_length)

    headers = {}
    if uploads:
        params = [("media[]", open(upload, 'rb')) for upload in uploads]
        params.append(("status", text))
        datagen, headers = multipart_encode(params)
        body = "".join(datagen)
        request_path = "/statuses/update_with_media.json"
    else:
        request_path = "/statuses/update.json"
        body = urllib.urlencode([("status", text)])

    resp, content = send_request(
            request_path,
            "POST",
            post_body=body,
            http_headers=headers)

    print "Done"


def get_url_length(url, config):
    """Depending on the protocol, there are two lengths for urls.
    short_url_length_https and short_url_length.

    :raises:
        RuntimeError: If url protocol is neither http nor https
    """
    if url.startswith("https://"):
        twitter_config["url_length"] = config["short_url_length_https"]
    elif url.startswith("http://"):
        twitter_config["url_length"] = config["short_url_length"]
    else:
        raise RuntimeError("Invalid protocol for url: %s" % url)

    return url_length


def send_request(request_path, http_method, post_body="", http_headers=None):
    """Send oauth authorized request to twitter REST api

    :param request_path:
        Request endpoint
    :param http_method:
        HTTP method for REST api
    :param post_body:
        Http request parameters

    :returns:
        A tuple of http response and content
    :raises:
        RuntimeError: Failed http request
    """
    url_base = "https://{host}/{api_version}".format(
            host=_config["rest_host"],
            api_version=_config["api_version"])
    url = url_base + request_path

    consumer = oauth.Consumer(key=_config["api_key"],
            secret=_config["api_secret"])
    token = oauth.Token(key=_config["access_token"],
            secret=_config["access_token_secret"])
    client = oauth.Client(consumer, token)

    resp, content = client.request(url,
            method=http_method,
            body=post_body,
            headers=http_headers)
    content = json.loads(content)

    # Raise exception if request not successful
    if resp.status < 200 or resp.status >= 300:
        error_msg = ""
        for error in content.get("errors", []):
            error_msg += "\n" + error.get("message", "")
        raise RuntimeError(
                "Request failed with error code {code}."
                "{message}".format(code=resp.status, message=error_msg))

    return resp, content


if __name__ == "__main__":
    main()

