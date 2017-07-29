# pywaschedv

### Install Instructions
 - Clone repository, and navigate to top level project folder
 - Create virtual environment using `virtualenv env`
 - Activate env using `source env/bin/activate`
 - Install requirements using `pip install -r requirements.txt`
 
 ### PyCharm
 I'd also highly recommend using PyCharm, best way to set up (imho ;)) is as follows:
 - Get repository `sudo add-apt-repository ppa:mystic-mirage/pycharm`
 - `sudo update`
 - `sudo apt-get install pycharm-community`
 
 Once it's installed, open the pywaschedv top level as an existing project. Then change the Python Interpreter to our virtual environment by going to *File->Settings...->Project:->Project Interpreter*. Choose the virtual env from the drop down combobox.
 
 To setup the debug environment, go to *Run->Edit Configurations...*. Press the green + icon, and then choose Python from the listed options. Set the configuration name (Django Debug Config, or something sensible). Under the configuration tab, set the Script to the **full path** of the 'manage.py' file, and the script parameters to 'runserver'. You can then run the server with full debug support by pressing the debug buttons in the IDE. 
