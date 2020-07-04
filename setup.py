import codecs
import re
from setuptools import find_packages, setup

version_regex = r'__version__ = ["\']([^"\']*)["\']'
with open('starlette_jsonapi/__init__.py', 'r') as f:
    text = f.read()
    match = re.search(version_regex, text)

    version = match.group(1)

readme = codecs.open('README.md', encoding='utf-8').read()

setup(
    name='starlette_jsonapi',
    version=version,
    description='Tiny wrapper on starlette and marshmallow-jsonapi for fast JSON:API compliant python services.',
    author='Vlad Stefan Munteanu',
    author_email='vladstefanmunteanu@gmail.com',
    long_description=readme,
    packages=find_packages(),
    package_data={'': ['LICENSE', 'README.md']},
    include_package_data=True,
    license='MIT License',
    url='https://github.com/vladmunteanu/starlette-jsonapi',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Internet :: WWW/HTTP',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    zip_safe=False,
)