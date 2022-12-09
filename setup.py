"""
Installs:
    - structmeta
"""

from setuptools import setup
from setuptools import find_packages

setup(
    name="structmeta",
    version="0.6",
    description="",
    long_description="",
    long_description_content_type="text/markdown",
    author="Karl-Ulrich Krägelin",
    author_email="kraegelin@sub.uni-goettingen.de",
    url="https://gitlab.gwdg.de/maps/mmservice",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    install_requires=open("requirements.txt").read().split("\n"),
    entry_points={
        "console_scripts": [
            "structmeta=structmeta:main",
        ]
    },
)
