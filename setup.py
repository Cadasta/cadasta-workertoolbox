import codecs
import os
import re
from setuptools import setup, find_packages, Command


###

NAME = 'cadasta-workertoolbox'
META_PATH = os.path.join("cadasta", "workertoolbox", "__init__.py")
PACKAGES = find_packages()
CLASSIFIERS = [
    "Development Status :: 3 - Alpha",
]
###


def read(*parts):
    """
    Build an absolute path from *parts* and and return the contents of the
    resulting file.  Assume UTF-8 encoding.
    """
    cur_dir = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(cur_dir, *parts), "rb", "utf-8") as f:
        return f.read()


META_FILE = read(META_PATH)


def find_meta(meta):
    """
    Extract __*meta*__ from META_FILE.
    """
    meta_match = re.search(
        r"^__{meta}__ = ['\"]([^'\"]*)['\"]".format(meta=meta),
        META_FILE, re.M
    )
    if meta_match:
        return meta_match.group(1)
    raise RuntimeError("Unable to find __{meta}__ string.".format(meta=meta))


class CleanCommand(Command):
    """ Custom clean command to tidy up the project root. """
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        os.system('rm -vrf ./build ./dist ./*.pyc ./*.tgz ./*.egg-info')


if __name__ == "__main__":
    setup(
        name=NAME,
        packages=PACKAGES,
        classifiers=CLASSIFIERS,

        version=find_meta('version'),
        description=find_meta('description'),
        author=find_meta('author'),
        author_email=find_meta('email'),
        license=find_meta('license'),

        long_description=read('README.md'),

        install_requires=[
            "SQLAlchemy<=1.1.11",
            "boto3<=1.4.4",
            "celery<=4.0.2",
            "kombu<=4.0.3",
            "psycopg2<=2.7.1",
        ],
        dependency_links=[
            "git+https://github.com/celery/kombu.git@master#egg=kombu-4.0.3"
        ],

        cmdclass={
            'clean': CleanCommand,
        }
    )
