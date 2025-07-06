            oauth = OAuth(app)
            google = oauth.register(
                name='google',
                client_id=app.config['GOOGLE_CLIENT_ID'],
                client_secret=app.config['GOOGLE_CLIENT_SECRET'],
                server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
                client_kwargs={
                    'scope': 'openid email profile https://www.googleapis.com/auth/gmail.send',
                    'access_type': 'offline',
                    'prompt': 'consent'
                }
            )