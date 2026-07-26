"""Drive EXIF -> visits. OWNER D. Merge Unified API, File Storage category.

Value: places visited with NO booking trail — the ones no email knows about.
Only write a row when you have BOTH a timestamp and a geotag. Anything else is
noise.
"""


def sync(limit: int = 200) -> int:
    """Drive images -> EXIF timestamp + GPS -> reverse-geocode -> visit rows
    with source='drive_exif', status='attended_unbooked'."""
    raise NotImplementedError
