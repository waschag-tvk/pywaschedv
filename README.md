# pywaschedv

## Install Instructions

In all the methods below, you first please clone this repository, and navigate
to top level project folder.

### Quickest way

Using [pipenv](https://docs.pipenv.org/install/), you just need to run
`pipenv install`.
Run Django by `pipenv run python manage.py <options see under "Usage">` or you
can enter a shell by `pipenv shell` and you don’t need to prefix `pipenv run`.

### Traditional way

 - Create virtual environment using `virtualenv env`
 - Activate env using `source env/bin/activate`
 - Install requirements using `pip install -r requirements.txt`

### If you have a very old distribution

If you have something like Debian Wheezy, installing either virtualenv or
python>=3.5 is not that easy, you can use conda.

 - Install miniconda from [conda.io](https://conda.io/miniconda.html)
 - Start a new shell (e. g. run `bash`)
 - Create a conda environment by
   `conda create -n <some name for your pywaschedv environment> python=3`
 - Enter the environment with `source activate <the pywaschedv environment name>`

### Alternative way on a very old Debian distribution (deprecated)

This method works, but is rather hacky and not recommended.

 - Create a [pbuilder](https://wiki.ubuntu.com/PbuilderHowto) chroot
   environment by
   `cowbuilder --create --distribution stretch --basepath /var/cowdancer/stretch`
 - Enter the chroot environment by
   `cowbuilder --login --basepath /var/cowdancer/stretch --bindmounts "$HOME"`
   The reason for mounting HOME is to access the git repository and created
   virtualenvs.
 - Create a user with the same username with `adduser <username>`
 - Login as user `su - <username>`
 - Install necessary things for any of the above methods to get started

## Additional setup to be done before use

The repository does not contain all migration files.
Therefore before first use of your instance, run

```
python manage.py makemigrations
python manage.py migrate
```

Further, quick setup of a waschuser for god and three machines as
required at TvK you can navigate to
`http://localhost:$DJANGO_PORT/wasch/setup/`.
You need to login as superuser (change password for WaschRoss in
[GodOnlyBackend](wasch/auth.py) as required).
As GodOnlyBackend depends on crypt, it only works in a POSIX
environment.
You can alternatively create a different superuser using `manage.py`.
This method has not been rigorously tested yet though.

All created machines are initially disabled.
Enable them as appropriate using the Django admin.
 
 ### Usage
 
 Like any django project you can start it with
 
 ```
 python manage.py runserver $SOME_PORT
 ```
 
 ### PyCharm
 I'd also highly recommend using PyCharm, best way to set up (imho ;)) is as follows:
 - Get repository `sudo add-apt-repository ppa:mystic-mirage/pycharm`
 - `sudo update`
 - `sudo apt-get install pycharm-community`
 
 Once it's installed, open the pywaschedv top level as an existing project. Then change the Python Interpreter to our virtual environment by going to *File->Settings...->Project:->Project Interpreter*. Choose the virtual env from the drop down combobox.
 
 To setup the debug environment, go to *Run->Edit Configurations...*. Press the green + icon, and then choose Python from the listed options. Set the configuration name (Django Debug Config, or something sensible). Under the configuration tab, set the Script to the **full path** of the 'manage.py' file, and the script parameters to 'runserver'. You can then run the server with full debug support by pressing the debug buttons in the IDE. 

## enteapi

For development of a remote desktop application for the activation of
appointments, pywaschedv provides the enteapi RESTful API based on the
Django REST framework.

Usage:

```python
import requests
# get available appointments
appointments = requests.get('http://localhost/enteapi/v1/appointment/').json()
# authenticate
token = requests.post(
    'http://localhost/enteapi/token-auth/',
    json={"username": "Me", "password": "secret123"},
    ).json()['token']
pk = appointments[0]['pk']
# activate the first available appointment
requests.post(
    'http://localhost/enteapi/v1/appointment/{:d}/activate/'.format(pk),
    json={"enteId": 1},
    headers={'Authorization': 'JWT ' + token})
# bonus: see the latest actual users for each machine
requests.get(
    'http://localhost/enteapi/v1/appointment/last_used_for_each_machine/')
```
