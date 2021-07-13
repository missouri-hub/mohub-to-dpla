from dateutil import parser
import pandas as pd
import requests
from iso639 import languages
from urllib.parse import urlparse

def get_metadata(field, metadata):
    """
    Returns metadata based on a field key.
    Subfields are delimited by periods, so we have to recursively loop through metadata fields to get them.

    :param field: a field key, possibly delimited by a period (for subfields)
    :param metadata: metadata object from OAI feed.
    :return: array of values for given field key
    """

    stack = field.split('.')
    _metadata = metadata
    for s in stack:
        if s not in _metadata:
            return False
        _metadata = _metadata[s]
    out = []

    for m in _metadata:
        out.extend([" ".join(a.strip().split()) for a in m.split(";") if a])
    return out

def generate_cdm_thumbnail(url):
    try:
        collection = url.split("/")[url.split("/").index("collection") + 1]
    except ValueError as e:
        print(url)
        raise
    record_id = url.split("/")[-1]
    o = urlparse(url)
    base = "{}://{}".format(o.scheme, o.netloc)
    thumbnail = "{}/utils/getthumbnail/collection/{}/id/{}".format(base, collection, record_id)

    return thumbnail

def parse_language(language_list):
    outlist = []
    delimiters = ['/', ',', ';']
    ll = []
    delimited = False
    for language in language_list:
        for d in delimiters:
            if d not in language:
                continue
            delimited = True
            for l in language.split(d):
                if l.strip() not in ll:
                    ll.append(l.strip())
        if not delimited:
            ll.append(language.strip())
        delimited = False
    language_list = ll
    for language in language_list:
        language_found = False
        codes = ['name', 'part3', 'part2b', 'part2t', 'part1']
        for code in codes:
            if code == 'name':
                language = language.capitalize()
            else:
                language = language.lower()
            try:
                lng = eval("languages.get({}='{}')".format(code, language))
                outlist.append({f"iso639_3": lng.part3, "name": lng.name})
                language_found = True
                break
            except (KeyError, SyntaxError) as e:
                continue

    return outlist

def parse_date(datestr):
    """
    Parses a string that may or may not be able to be converted to a datetime object.
    If able to be parsed, returns a string corresponding to the datetime template <Month> <day>, <Year>

    :param datestr: string representing a potential datetime object
    :return: a formatted date string
    """

    try:
        parsed = parser.parse(datestr)
    except ValueError as e:
        print(f"{datestr} could not be parsed as a date. Skipping.")
        return False

    return parsed.strftime("%B %-d, %Y")

def make_list_flat(l):
    """
    Flattens a list of lists, for cleaning purposes

    :param l: a list of lists
    :return: a list of not-list values
    """

    flist = []
    flist.extend([l]) if (type(l) is not list) else [flist.extend(make_list_flat(e)) for e in l]
    return flist


def split_values(row):
    """
    Split fields with semicolons into arrays

    :param row: a row of metadata
    :return: same row of metadata but with certain fields converted to arrays
    """

    fields_to_split = [
        'subject',
        'date',
        'language'
    ]
    for field, value in row.items():
        if field not in fields_to_split:
            continue
        outval = []
        for v in value:
            outval.extend([_v.strip() for _v in v.split(";") if _v != ''])
        row[field] = outval

    return row


def write_csv(data, outpath):
    """
    Helper function to output harvested metadata as a more human-readable CSV file

    :param data: harvested JSON data from an institution
    :param outpath: file path for CSV output
    :return: nothing
    """
    out = []
    for row in data:
        outrow = {}
        outrow["url"] = row["isShownAt"]
        outrow["dataProvider"] = row["dataProvider"]
        outrow["thumbnail"] = row["object"]
        outrow["dplaIdentififer"] = row["@id"]
        for field, val in row["sourceResource"].items():
            if field == "identifier":
                continue
            if type(val) == list:
                if len(val) == 0:
                    outrow[field] = ""
                elif field == "subject":
                    outrow[field] = "|".join([subj["name"] for subj in val])
                elif field == "temporal":
                    outrow["displayDate"] = val[0]["displayDate"]
                elif field == "language":
                    outrow["languageCode"] = "|".join([l["iso639_3"] for l in val])
                    outrow["language"] = "|".join([l["name"] for l in val])
                elif len(val) == 1:
                    outrow[field] = val[0]
                elif len(val) > 1:
                    outrow[field] = "|".join(val)
            else:
                outrow[field] = val
        out.append(outrow)
    outdf = pd.DataFrame(out)
    outdf.to_csv(outpath, index=False)

def get_datadump(url):
    """
    If an institution is providing a data dump instead of an OAI feed, we simply download and return the JSON.

    :param url: url to a JSON file
    :return: record metadata from file
    """
    res = requests.get(url)
    return res.json()['records']

