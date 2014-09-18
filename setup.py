from setuptools import setup

with open('README.rst') as file:
    long_description = file.read()

setup(
    name='django-requirejs',
    version='0.1.dev0',
    url='http://github.com/bpeschier/django-requirejs',
    author="Bas Peschier",
    author_email="bpeschier@fizzgig.nl",
    py_modules=['requirejs', ],
    license='MIT',
    long_description=long_description,
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    install_requires=['Django>=1.6', 'django_compressor>=1.4'],
)