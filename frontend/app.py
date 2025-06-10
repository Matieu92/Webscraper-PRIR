import os
from flask import Flask

print("Loading app.py")  # Debug

def create_app(test_config=None):
    print("Creating app instance")  # Debug
    app = Flask(__name__, instance_relative_config=True, template_folder='templates', static_folder='static')
    app.config.from_mapping(
        SECRET_KEY='dev',
    )
    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
        print(f"Created instance path: {app.instance_path}")  # Debug
    except OSError:
        print(f"Instance path already exists: {app.instance_path}")  # Debug

    from . import scraper
    print("Registering scraper")  # Debug
    app.register_blueprint(scraper.bp)
    app.add_url_rule('/', endpoint='index')  # Upewnij się, że endpoint 'index' jest powiązany z scraper.index

    return app

if __name__ == '__main__':
    print("Running app directly")  # Debug
    app = create_app()
    app.run(debug=True)