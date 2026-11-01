from glob import glob
from setuptools import setup
from owrx.version import looseversion

try:
    from setuptools import find_namespace_packages
except ImportError:
    from setuptools import PEP420PackageFinder

    find_namespace_packages = PEP420PackageFinder.find

setup(
    name="OpenWebRX",
    version=str(looseversion),
    packages=find_namespace_packages(
        include=[
            "owrx*",
            "csdr*",
            "htdocs",
        ]
    ),
    package_data={"htdocs": [f[len("htdocs/") :] for f in glob("htdocs/**/*", recursive=True)]},
    entry_points={"console_scripts": ["openwebrx=owrx.__main__:main"]},
    url="https://www.openwebrx.de/",
    author="Marat Fayzullin",
    author_email="luarvique@gmail.com",
    maintainer="Marat Fayzullin",
    maintainer_email="luarvique@gmail.com",
    license="GAGPL",
    python_requires=">=3.5",
    install_requires=["packaging"],
)
