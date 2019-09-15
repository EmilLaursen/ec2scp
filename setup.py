from setuptools import setup, find_packages

setup(
    name='ec2scp',
    version='0.1',
    py_modules=find_packages(),
    include_package_date=True,
    python_requires='>=3.5',
    install_requires=[
        'Click',
        'boto3',   
    ],
    entry_points='''
        [console_scripts]
        ec2scp=powah_scp:scp
    ''',
)