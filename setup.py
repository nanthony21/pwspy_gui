# Copyright 2018-2020 Nick Anthony, Backman Biophotonics Lab, Northwestern University
#
# This file is part of PWSpy.
#
# PWSpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PWSpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PWSpy.  If not, see <https://www.gnu.org/licenses/>.

# -*- coding: utf-8 -*-
"""
This file is used to install the pwspy package. for example navigate in your terminal to the directory containing this
file and type `pip install .`. This file is also used by the Conda recipe (buildscripts/conda)
"""
import pathlib
from setuptools import setup, find_packages
import setuptools_scm

HERE = pathlib.Path(__file__).parent  # The directory containing this file
README = (HERE / "README.md").read_text()  # The text of the README file

setup(name='pwspy_gui',
      version=setuptools_scm.get_version(write_to="src/pwspy_gui/version.py"),
      description='A collection of GUIs providing users with easy access to PWS data analysis.',
      long_description=README,
      long_description_content_type="text/markdown",
      author='Nick Anthony',
      author_email='nicholas.anthony@northwestern.edu',
      url='https://bitbucket.org/backmanlab/pwspy_gui/src/master/',
      python_requires='>=3.7',
      install_requires=['numpy',
                        'matplotlib',
                        'psutil',
                        'shapely',
                        'pandas',
                        'jsonschema',
                        'google-api-python-client',
                        'google-auth-httplib2',
                        'google-auth-oauthlib',
                        'PyQt5',
                        'pwspy',  # Core pws package, available on backmanlab anaconda cloud account.
                        'mpl_qt_viz>=1.0.5'],  # Plotting package available on PyPi and the backmanlab anaconda cloud account. Written for this project by Nick Anthony
      package_dir={'': 'src'},
      package_data={'pwspy_gui': ['_resources/*',
                              'PWSAnalysisApp/_resources/*']},
      packages=find_packages('src'),
	  entry_points={'gui_scripts': [
          'PWSAnalysis = pwspy_gui.PWSAnalysisApp.__main__:main',
          "ERCreator = pwspy_gui.ExtraReflectanceCreator.__main__:main"
      ]}
	)
