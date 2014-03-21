from fabric.api import *
import fabric.contrib.files

env.use_ssh_config = True
DEPLOY_DIR = '/opt/openstax'
RVM = '{}/.rvm/scripts/rvm'.format(DEPLOY_DIR)
PHANTOMJS = '{}/phantomjs-1.9.7-linux-x86_64/bin'.format(DEPLOY_DIR)

def _setup():
    if not fabric.contrib.files.exists(DEPLOY_DIR):
        run('mkdir -p {}'.format(DEPLOY_DIR))
    with cd(DEPLOY_DIR):
        sudo('apt-get update')
        sudo('apt-get install --yes git')
        _setup_rvm()

def _setup_rvm():
    with cd(DEPLOY_DIR):
        if not fabric.contrib.files.exists(RVM):
            run('wget -q -O - https://get.rvm.io | bash -s -- --ignore-dotfiles')
            run ('mv ~/.rvm .')

def _setup_ssl():
    with cd(DEPLOY_DIR):
        if not fabric.contrib.files.exists('server.crt'):
            run('openssl genrsa -des3 -passout pass:x -out server.pass.key 2048')
            run('openssl rsa -passin pass:x -in server.pass.key -out server.key')
            run('rm server.pass.key')
            run('openssl req -new -key server.key -out server.csr')
            run('openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt')

def _setup_phantomjs():
    with cd(DEPLOY_DIR):
        if not fabric.contrib.files.exists('phantomjs-1.9.7-linux-x86_64'):
            run("wget 'https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-1.9.7-linux-x86_64.tar.bz2'")
            run('tar xf phantomjs-1.9.7-linux-x86_64.tar.bz2')

def accounts_setup():
    _setup()
    with cd(DEPLOY_DIR):
        _setup_ssl()
        _setup_phantomjs()
        if not fabric.contrib.files.exists('accounts'):
            run('git clone https://github.com/openstax/accounts')
        with cd('accounts'):
            with prefix('source {}'.format(RVM)):
                run('rvm install ruby-1.9.3-p392')
                run('rvm gemset create accounts')
                run('rvm gemset use accounts')
                run('bundle install --without production')
                run('rake db:setup', warn_only=True)
        print """
To use the facebook and twitter login:

1. Create an app on facebook and twitter

2. Paste the "App ID" and "App Secret" from the facebook app settings page into accounts/config/secret_settings.yml:
   facebook_app_id: '1234567890'
   facebook_app_secret: '1234567890abcdef'

   Paste the "Consumer Key" and "Consumer Secret" from the twitter app settings page into accounts/config/secret_settings.yml:
   twitter_consumer_key: 'xxxxx'
   twitter_consumer_secret: 'yyyyy'

3. Set the callback url on the facebook and twitter app settings page to https://{server}:3000/auth/facebook and https://{server}:3000/auth/twitter respectively. (or the IP address of {server})

""".format(server=env.host)

def accounts_run():
    with cd(DEPLOY_DIR):
        with cd('accounts'):
            with prefix('source {}'.format(RVM)):
                run('rake db:migrate')
                # ctrl-c doesn't kill the rails server so the old server is still running
                run('kill -9 `cat tmp/pids/server.pid`', warn_only=True)
                run('rails server')

def accounts_run_ssl():
    with cd(DEPLOY_DIR):
        with cd('accounts'):
            with prefix('source {}'.format(RVM)):
                run('thin start -p 3000 --ssl --ssl-verify --ssl-key-file {dir}/server.key --ssl-cert-file {dir}/server.crt'.format(dir=DEPLOY_DIR))

def accounts_test(test_case=None):
    with cd(DEPLOY_DIR):
        with cd('accounts'):
            with prefix('source {}'.format(RVM)):
                if test_case:
                    run('PATH=$PATH:{} rspec {}'.format(PHANTOMJS, test_case))
                else:
                    run('PATH=$PATH:{} rake'.format(PHANTOMJS))

def accounts_routes():
    with cd(DEPLOY_DIR):
        with cd('accounts'):
            with prefix('source {}'.format(RVM)):
                run('rake routes')

def example_setup():
    _setup()
    with cd(DEPLOY_DIR):
        sudo('apt-get install --yes nodejs')
        if not fabric.contrib.files.exists('connect-rails'):
            run('git clone https://github.com/openstax/connect-rails')
        with cd('connect-rails'):
            with prefix('source {}'.format(RVM)):
                run('rvm install ruby-1.9.3-p392')
                run('rvm gemset create connect-rails')
                run('rvm gemset use connect-rails')
                run('bundle install --without production')
        pwd = run('pwd')
        filename = 'connect-rails/lib/openstax/connect/engine.rb'
        if not fabric.contrib.files.contains(filename, ':client_options'):
            fabric.contrib.files.sed(filename,
                    'OpenStax::Connect.configuration.openstax_application_secret',
                    'OpenStax::Connect.configuration.openstax_application_secret, '
                    '{:client_options => {:ssl => {:ca_file => "%s/server.crt"}}}' % pwd)
        with cd('connect-rails/example'):
            with prefix('source {}'.format(RVM)):
                run('rake db:setup', warn_only=True)
                run('rake openstax_connect:install:migrations')

        print """
To set up openstax/connect-rails with openstax/accounts:

1. Go to http://{server}:2999/oauth/applications

2. Create a "New application" with callback url: "http://{server}:4000/connect/auth/openstax/callback"

3. Click the "Trusted?" checkbox and submit

4. Copy the application ID and secret into connect-rails/example/config/secret_settings.yml, for example:
   openstax_application_id: '54cc59280662417f2b30c6869baa9c6cb3360c81c4f9d829155d2485d5bcfeed'
   openstax_application_secret: '7ce94d06d7bc8aec4ff81c3f65883300e1e2fa10051e60e58de6d79de91d8608'

5. Set config.openstax_services_url in connect-rails/example/config/initializers/openstax_connect.rb to "https://{server}:3000/" (or the IP address of {server})

6. Start the example application.

7. Go to http://{server}:4000 and click log in

See https://github.com/openstax/connect-rails for full documentation.
""".format(server=env.host)

def example_run():
    with cd(DEPLOY_DIR):
        with cd('connect-rails/example'):
            with prefix('source {}'.format(RVM)):
                run('rake db:migrate')
                # ctrl-c doesn't kill the rails server so the old server is still running
                run('kill -9 `cat tmp/pids/server.pid`', warn_only=True)
                run('rails server')
