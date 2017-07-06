import os
import re
import sys
from setuptools import setup, find_packages, Command


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("^__version__ = ['\"]([^'\"]+)['\"]",
                     init_py, re.MULTILINE).group(1)


def get_pkg_from_git_url(link):
    """
    Given a pip-compatible git-requirement, output a setup.py-compatible
    install requirement.

    >>> get_pkg_from_git_url('git+https://github.com/user/pkg.git@branch')
    'pkg'
    """
    try:
        link = link.split('#')[0].strip()
        end = link.split('/')[-1]
        pkg, version = end.split('@', 1)
        pkg = pkg.split('.git')[0]
        return pkg
    except:
        sys.stderr.write("Failed on link {!r}\n".format(link))
        raise


def get_dependency_from_git_url(link):
    """
    Given a pip-compatible git-requirement, output a setup.py-compatible
    dependency link.

    >>> get_dependency_from_git_url('git+https://github.com/user/pkg.git@branch')
    'https://github.com/user/pkg/tarball/branch#egg=pkg'
    """
    try:
        link = link.split('#')[0].strip()
        link = link.replace('git+', '')
        link, branch = link.split('@', 1)
        link = link.replace('.git', '')
        pkg = link.split('/')[-1]
        link = '{}/tarball/{}'.format(link, branch)
        if '#egg=' not in link:
            link = "{}#egg={}".format(link, pkg)
        return link
    except:
        sys.stderr.write("Failed on link {!r}\n".format(link))
        raise


class CleanCommand(Command):
    """ Custom clean command to tidy up the project root. """
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        os.system('rm -vrf ./build ./dist ./*.pyc ./*.tgz ./*.egg-info')


with open('./requirements.txt') as f:
    raw_requirements = f.read().splitlines()


setup(
    name='cadasta-workertoolbox',

    version=get_version('cadasta/workertoolbox'),

    description='Cadasta Worker Toolbox',
    long_description=(
        'A collection of helpers for use in creating message consumers '
        'for the Cadasta system.'
    ),

    author='Anthony Lukach',
    author_email='alukach@cadasta.org',

    license='GNU Affero General Public License v3.0',

    packages=find_packages(),

    install_requires=[
        (req if '://' not in req.split('#')[0] else get_pkg_from_git_url(req))
        for req in raw_requirements
    ],
    dependency_links=[
        get_dependency_from_git_url(req)
        for req in raw_requirements if '://' in req.split('#')[0]
    ],

    cmdclass={
        'clean': CleanCommand,
    }
)
