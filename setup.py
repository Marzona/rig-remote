from setuptools import setup, find_packages
import os
import sys

def readme():
    with open('README.md') as f:
        return f.read()

if sys.argv[-1] == 'test':
    test_requirements = [
        'pytest',
        'flake8',
        'coverage'
    ]
    try:
        modules = map(__import__, test_requirements)
    except ImportError as e:
        err_msg = e.message.replace("No module named ", "")
        msg = "%s is not installed. Install your test requirments." % err_msg
        raise ImportError(msg)
    os.system('py.test --cov-report term-missing  --cov rig_remote')
    sys.exit()


if sys.argv[-1] == 'publish':
    os.system("python setup.py sdist upload")
#    os.system("python setup.py bdist_wheel upload")
    print("You probably want to also tag the version now:")
    print("  git tag -a %s -m 'version %s'" % (version, version))
    print("  git push --tags")
    print(" or use the tag option with this script.")
    sys.exit()

if sys.argv[-1] == 'tag':
    os.system("git tag -a %s -m 'version %s'" % (version, version))
    os.system("git push --tags")
    sys.exit()

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

