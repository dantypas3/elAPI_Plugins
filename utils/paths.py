import os

"""

Created for: Universität Heidelberg – BZH - SFB 1638
Author: Dionysios Antypas (dionysios.antypas@bzh.uni-heidelberg.de)
Status: Work in progress

"""

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def export_json(*args):
    return os.path.join(BASE_DIR, 'json_exports', *args)