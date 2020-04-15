import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="brang",
    version="1.0.0",
    author="Dirk Schäfer",
    author_email="method.scientist@gmail.com",
    description="Website Tracker",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    python_requires='==3.6.6',
    scripts=['bin/brang'],
)
