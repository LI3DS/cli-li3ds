# -*- coding: utf-8 -*-
import os
import re
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

requirements = (
    'requests==2.13.0',
    'cliff==2.6.0',
    'requests==2.13.0',
    'pytz==2017.2',
    'pyquaternion==0.9.0',
    'python-dateutil==2.6.0'
)

dev_requirements = (
    'pytest',
)

doc_requirements = (
)

prod_requirements = (
)


def find_version(*file_paths):
    """
    see https://github.com/pypa/sampleproject/blob/master/setup.py
    """
    with open(os.path.join(here, *file_paths), 'r') as f:
        version_file = f.read()

    # The version line must have the form
    # __version__ = 'ver'
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string. "
                       "Should be at the first line of __init__.py.")


setup(
    name='cli_li3ds',
    version=find_version('cli_li3ds', '__init__.py'),
    description="Scripts to import data into the li3ds database",
    url='https://github.com/LI3DS/cli-li3ds',
    author='dev',
    author_email='contact@oslandia.com',
    license='GPLv3',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    packages=find_packages(),
    install_requires=requirements,
    include_package_data=True,
    extras_require={
        'dev': dev_requirements,
        'prod': prod_requirements,
        'doc': doc_requirements
    },
    entry_points={
        'console_scripts': [
            'li3ds = cli_li3ds.main:main',
        ],
        'li3ds': [
            'import-extcalib = cli_li3ds.import_extcalib:ImportExtCalib',
            'import-autocal = cli_li3ds.import_autocal:ImportAutocal',
            'import-ori = cli_li3ds.import_ori:ImportOri',
            'import-orimatis = cli_li3ds.import_orimatis:ImportOrimatis',
            'import-image = cli_li3ds.import_image:ImportImage',
            'import-sbet= cli_li3ds.import_sbet:ImportSbet',
            'import-ept = cli_li3ds.import_ept:ImportEpt',
            'import-platform = cli_li3ds.import_platform:ImportPlatform',
            'import-json = cli_li3ds.import_json:ImportJson',
        ]
    }
)
