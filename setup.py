from setuptools import setup

with open('README.rst') as file:
    long_description = file.read()

setup(
    name='django-compressor-requirejs',
    version='0.2',
    url='http://github.com/bpeschier/django-compressor-requirejs',
    author="Bas Peschier",
    author_email="bpeschier@fizzgig.nl",
    py_modules=['requirejs', ],
    license='MIT',
    long_description=long_description,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    install_requires=['Django>=1.6', 'django_compressor>=1.4'],
)