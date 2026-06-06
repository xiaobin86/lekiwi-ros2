from setuptools import find_packages, setup

package_name = 'lekiwi_teleop'

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
    description='PC端遥操作节点：手柄 → /cmd_vel',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'teleop_node = lekiwi_teleop.teleop_node:main',
            'custom_joy_node = lekiwi_teleop.custom_joy_node:main',
        ],
    },
)
