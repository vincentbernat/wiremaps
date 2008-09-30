import sys
import twisted
from distutils.core import setup, Extension
from wiremaps import VERSION

def refresh_plugin_cache():
    from twisted.plugin import IPlugin, getPlugins
    list(getPlugins(IPlugin))

if __name__ == "__main__":
    setup(name="wiremaps",
          version=VERSION,
          classifiers = [
            'Development Status :: 4 - Beta',
            'Environment :: No Input/Output (Daemon)',
            'Environment :: Web Environment',
            'Framework :: Twisted',
            'Intended Audience :: System Administrators',
            'License :: OSI Approved :: GNU General Public License (GPL)',
            'Operating System :: POSIX',
            'Programming Language :: Python',
            'Topic :: System :: Networking',
            ],
          url='https://trac.luffy.cx/wiremaps/',
          description='layer 2 network discovery application',
          author='Vincent Bernat',
          author_email="bernat@luffy.cx",
          ext_modules= [
            Extension('wiremaps.collector.snmp',
                      libraries = ['netsnmp', 'crypto'],
                      sources= ['wiremaps/collector/snmp.c']),
            ],
          packages=["wiremaps", "wiremaps.collector", "wiremaps.web",
                    "twisted.plugins"],
          package_data={'twisted': ['plugins/wiremaps_plugin.py'],
                        'wiremaps.web': ["static/*.png", "static/*.css", "static/*.js",
                                         "main.xhtml",
                                         "images/1.*.png", "images/unknown.png"],},
          )
    # refresh_plugin_cache()
