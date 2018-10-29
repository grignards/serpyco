from setuptools import setup
from Cython.Build import cythonize

requires = ["python-dateutil", "rapidjson", 'dataclasses;python_version<"3.7"']


setup(
    name="dataclasses-serializer",
    description="Fast serialization of dataclasses",
    author="Sébastien Grignard",
    author_email="pub@amakaze.org",
    url="https://gitlab.com/sgrignard/dataclasses-serializer",
    install_requires=requires,
    tests_require=["pytest", "flake8", "mypy"],
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
    ext_modules=cythonize("dataclasses_serializer.pyx"),
)
