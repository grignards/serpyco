# -*- coding: utf-8 -*-

from setuptools import Extension, setup

requires = ["python-dateutil", "python-rapidjson", "dataclasses;python_version<'3.7'"]

setup(
    name="serpyco",
    version="0.7",
    description="Fast serialization of dataclasses using Cython",
    author="Sébastien Grignard",
    author_email="pub@amakaze.org",
    url="https://gitlab.com/sgrignard/serpyco",
    setup_requires=[
        # Setuptools 18.0 properly handles Cython extensions.
        "setuptools>=18.0",
        "cython",
    ],
    install_requires=requires,
    tests_require=["pytest", "flake8"],
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries",
    ],
    ext_modules=[Extension("serpyco", sources=["serpyco.pyx"])],
    zip_safe=False,
)
