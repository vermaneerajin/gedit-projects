#!/usr/bin/python3
# -*- coding: utf-8 -*-

#  Copyright © 2012-2014, 2016  B. Clausius <barcc@gmx.de>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.


from glob import glob
from distutils.core import setup


setup(
    name='gedit-projects',
    version='1.3',
    license='GPL-3',
    author='B. Clausius',
    author_email='barcc@gmx.de',
    description='Manage projects in gedit',
    long_description=
'''For this plugin a project is just a directory path. A list of last opened
files is stored in the user config directory. In the project directory itself
no data is stored or changed by the plugin. In the sidebar are two lists:
 * Open Projects: projects with at least one open file
 * All projects: project directories that are known to the plugin,
   projects that contain subprojects are shown in a tree structure
In the context menu you can perform some actions, including:
 * Open Project: restore all recently opened files of a project
 * View Project Folder: the project folder is opened with the default program
 * Close Project: all project files are closed (the file list is preserved)
 * Add Folder, Remove Folder: specify which folders are known as a project
 * Find Subprojects: search within the project folder for nested projects
After installing and activating the plugin, you can invoke the settings
dialog. There you can set up a directory that can be scanned for projects.
Project directories are recognized by specific file names within the
directory like VCS folders or files for build systems.''',
    url='https://launchpad.net/gedit-projects',

    data_files=[
                ('lib/gedit/plugins/', ['projects.plugin']),
                ('lib/gedit/plugins/projects/', glob('projects/*.py')),
                ('lib/gedit/plugins/projects/', glob('projects/*.ui')),
                ('share/glib-2.0/schemas/', glob('*.gschema.xml')),
               ],
    )

