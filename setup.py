# -*- coding: utf-8 -*-

from setuptools import Extension, find_packages, setup

requires = [
    "python-dateutil",
    "python-rapidjson",
    "typing-inspect",
    "dataclasses;python_version<'3.7'",
]

with open("README.rst") as f:
    readme = f.read()

setup(
    name="serpyco",
    use_scm_version=True,
    description="Fast serialization of dataclasses using Cython",
    long_description=readme,
    author="Sébastien Grignard",
    author_email="pub@amakaze.org",
    url="https://gitlab.com/sgrignard/serpyco",
    packages=find_packages(),
    package_data={"serpyco": ["*.pyi", "py.typed"]},
    include_package_data=True,
    python_requires=">=3.6",
    setup_requires=[
        # Setuptools 18.0 properly handles Cython extensions.
        "setuptools>=18.0",
        "cython",
        "pytest-runner",
        "setuptools_scm",
        "wheel",
    ],
    install_requires=requires,
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Libraries",
    ],
    ext_modules=[
        Extension("serpyco.serializer", sources=["serpyco/serializer.pyx"]),
        Extension("serpyco.encoder", sources=["serpyco/encoder.pyx"]),
    ],
    zip_safe=False,
)
