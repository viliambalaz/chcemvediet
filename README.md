# Chcem vediet

Chcem vedieť -- Slovak for "I want to know" -- a server to ease access to information under the
[Slovak Freedom Of Information Act 211/2000 Coll](http://www.urzd.sk/legislativa/211-00-en.pdf).


## 1. Site Development

To develop and test the site locally on your computer you don't need any real webserver, database,
nor mail server. They are simulated by the testing environment.

Please make sure you won't push any autogenerated files to the git repository, such as your local
`env/` directory or `test.db` and `*.pyc` files.


### 1.1. Dependencies

You need the following packages installed
 * python (ver. 2.7.x)
 * python-virtualenv


### 1.2. Installation

To prepare your local development environment, run the following commands:

	$ git clone https://github.com/martinmacko47/chcemvediet.git
	$ cd chcemvediet
	$ virtualenv env
	$ env/bin/pip install -r requirements.txt
	$ env/bin/python manage.py syncdb --all --noinput
	$ env/bin/python manage.py migrate --fake
	$ env/bin/python manage.py loaddata fixtures/*


### 1.3. Updates

You should update your development environment regularly to reflect the changes made by other
developers. To update the
environment, you can delete it and recreate it from the scratch again, or you can migrate it.
Migrations are useful if you've got some unfinished work you have not pushed to the repository,
yet. However, you should recreate your environment from the scratch once in a while, as the
migrations are not waterproof and may fail sometimes, especially if migrating from a rather old
environment.

To migrate to an updated version of the site, run the following commands:

	$ cd chcemvediet
	$ git pull
	$ env/bin/pip install -r requirements.txt
	$ env/bin/python manage.py syncdb --noinput
	$ env/bin/python manage.py migrate


### 1.4. Viewing the site

 1. Run testing webserver:

    	$ cd chcemvediet
    	$ env/bin/python manage.py runserver

 2. Run testing mail infrastructure in another shell (see details in the next section):

    	$ cd chcemvediet
    	$ env/bin/python manage.py dummymail

 3. Navigate your browser to: http://127.0.0.1:8000/admin/socialaccount/socialapp/ and login as
    `admin` with password `kalerab`. Then click on 'Google OAuth' and enter your Google Apps
    'Client id' and 'Secret'. Similarly enter your secrets for LinkedIn, Twitter and Facebook.
    Don't forget to logout the admin interface afterwards.

 4. Now, you can navigate your browser to: http://127.0.0.1:8000/ and start using it.


### 1.5. Dummy e-mail infrastructure

Using the command:

	$ env/bin/python manage.py dummymail

you can create a dummy e-mail infrastructure for local development. For help on command options
run:

	$ env/bin/python manage.py help dummymail

This command runs two pairs of dummy SMTP and IMAP servers on localhost. One pair is for outgoing
mails and one for incoming mails. By default, outgoing SMTP server runs on port number 1025,
incoming SMTP server on port number 2025, outgoing IMAP server on port number 1143 and incoming
IMAP server on port number 2143. You may change these port numbers with options.

<p align="center">
  <img src="misc/dummymail.png" alt="Infrastructure diagram" />
</p>

During the development, you may use this infrastructure to simulate the site communication with the
outside world with no risk of sending any real e-mails to the outside world. In this setting, the
outside world will be represented by you, the site developer and/or tester. This means that all
e-mails sent from the site will be delivered to your IMAP client instead of their real destination.

The site sends its outgoing mails to the outgoing SMTP server and fetches its incoming mails from
the incoming IMAP server. On the other side, if you (representing the outside world) want to send
an email to the site, you have to send it to the incoming SMTP server. If you want to read the
mails sent by the site, you should fetch them from the outgoing IMAP server. Never try to connect
to outgoing SMTP server nor the incoming IMAP server. Only the site should connect to them. We run
two separate pairs of SMTP and IMAP servers in order to make sure the messages from the site will
not confuse with the messages from the outside world.

You may use any common IMAP e-mail client to connect to the incoming SMTP server and the outgoing
IMAP server. However, some e-mail clients (e.g. Thunderbird) get confused when the server
infrastructure restarts and refuse to fetch the messages any more. Restarting the client should
help. Sometimes, some clients (e.g. Thunderbird) refuse to fetch some messages for no apparent
reason, especially the first message. In such case, try some other client, or try to send the
message once again. The password for both the incoming SMTP server and the outgoing IMAP server is "aaa".

Note: No real e-mails are sent anywhere. The SMTP server is dummy and will never relay any received
message to any other SMTP server. Instead, it will store it locally in the memory and make it
available via dummy IMAP server. So, it's safe to send any message, from any e-mail address to any
e-mail address whatsoever. Nothing will be delivered. Also note, that all e-mails are stored in the
memory only, so they will disappear when the infrastructure is restarted.


## 2. Site Administration

In order to administrate the site you need to login as the admin. Navigate your
browser to: http://127.0.0.1:8000/admin and login as `admin` with password `kalerab`. You may
administer the site directly in the backend administration interface, or you may use the frontend
administration interface. To open the frontend administration interface click on 'Frontend
Administration' link in the top-right corner of the backend administration interface.


### 2.1 Content Administration

You can administer three kinds of content on the site:

 1. **CMS pages**. CMS pages are pages with static content like the site homepage or the page about
    the project. In order to administrate their content, login as the admin, open the frontend
    administration interface and navigate to the page you want to change. You will see a small
    white `+` icon in the top-right corner of the page. Click it to open the CMS Toolbar, and
    enable CMS Edit Mode. In CMS Edit Mode, you can edit all page content but its title. To change
    page's title click `Admin` / `Page settings` menu item in the top-right page corner to open the
    settings screen, where you can configure several page properties. Please, don't mess it up.
    Don't forget to publish the page after you finish editing it.

    Alternatively, you can administrate the pages directly in the backend administration interface.
    See http://127.0.0.1:8000/en/admin/cms/page/ .

 2. **CMS content on application pages**. Application pages, besides their generated content,
    contain lots of static content as well. You can edit it using the same frontend administration
    interface you edited CMS pages with. However, using the frontend administration interface you
    can only edit pages visible to the logged-in user. Therefore, for instance, you may not edit
    the 'Sign In' page here. Nonetheless, you may use the backend administration interface. See
    http://127.0.0.1:8000/en/admin/chunks/chunk/ where you can find all CMS chunks used by
    application pages.

 3. **Generated content on application pages**. The content generated by the application may only
    be changed in the application itself. To change the english translation, edit the application
    code and/or templates directly. To change the slovak translation, edit the localization `*.po`
    file stored in the `locale` directory.

    After you alter the application code, please regenerate the localization file:

    	$ cd chcemvediet/chcemvediet
    	$ ../env/bin/python ../manage.py makemessages -l sk

    Update the localization `*.po` file stored in `locale` directory and compile it:

    	$ cd chcemvediet/chcemvediet
    	$ ../env/bin/python ../manage.py compilemessages

    If you only change the localization `*.po` file, please, don't regenerate it, just compile it.

To upstream the changes you have done, you need to push them to the git repository. If you altered
the application code, template, and/or localization files, push them directly to the repository.
However, if you edited the CMS content, you will need to prepare fixtures that will be able to
reconstruct your CMS database and upstream the fixtures. To prepare the fixtures write;

	$ cd chcemvediet
	$ env/bin/python manage.py dumpdata --indent=2 cms text plaintext variable chunks > fixtures/cms.json

Before pushing the new fixtures to the git repository, please, check if they regenerate the
database correctly.

