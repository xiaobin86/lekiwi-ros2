from setuptools import find_packages, setup

package_name = 'lekiwi_base'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='acelan',
    maintainer_email='rabbitlxb@gmail.com',
    description='树莓派端底盘驱动节点：/cmd_vel → LeKiwi 底盘',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'base_node = lekiwi_base.base_node:main',
        ],
    },
)
