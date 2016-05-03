from setuptools import setup, find_packages

def readme():
    with open('README.md') as f:
        return f.read()

setup(
    name = "rig-remote",
    download_url = ["https://github.com/Marzona/rig-remote/releases"],
    version = "2.0",
    description = "Remote control a radio transceiver through RigCtl.",
    author="Simone Marzona",
    author_email="marzona@knoway.info",
    url = "https://github.com/Marzona/rig-remote/",
    packages = ["rig_remote"],
    long_description = """
        Rig-Remote is a tool for remotely control 
        a radio transceiver using RigCtl protocol over TCP/IP. 
        Rig Remote provides frequency scanning and monitoring,
        frequency bookmarks.
        """,
    classifiers = [
        "Programming Language :: Python",
        "Topic :: Communications",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Information Technology",
    ],
    keywords = "rigctl, ham, radio, bookmarks, scanner",
    license = "MIT",
    scripts = ['rig-remote.py'],
    setup_requires = ["pytest-runner",],
    tests_require = ["pytest",],
    include_package_data = True,
    install_requires = [
        "setuptools",
        "argparse",
        "logging",
        "datetime",
        "logging",
    ],
    zip_safe = False)

