__author__ = 'michel'
from setuptools import setup, find_packages

setup(name='comba_python',
      version='0.1',
      description='Comba python modules',
      long_description='Provides the controller, archiver, scheduler, monitor',
      url='https://gitlab.janguo.de/comba/comba-python-clientapi',
      author='Michael Liebler',
      author_email='michael-liebler@janguo.de',
      license='GPLv3',
      packages=find_packages(),
      zip_safe=False)
