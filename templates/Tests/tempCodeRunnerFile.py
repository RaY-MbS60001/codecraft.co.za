class ProductionConfig(Config):
    """Production configuration for deployment on Render"""
    # Handle Render's PostgreSQL URL
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or Config.SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }


def get_database_url():
    """
    Get the appropriate database URL for the environment
    Returns PostgreSQL URL for production, SQLite for development
    """
    # Handle Render PostgreSQL URL
    render_db_url = os.environ.get('DATABASE_URL', '')
    if render_db_url and render_db_url.startswith('postgres://'):
        render_db_url = render_db_url.replace('postgres://', 'postgresql://', 1)
    
    # Fallback to SQLite with absolute path for development
    if not render_db_url:
        base_dir = Path(__file__).resolve().parent
        instance_path = base_dir / 'instance'
        instance_path.mkdir(exist_ok=True, parents=True)
        sqlite_path = instance_path / 'app.db'
        return f'sqlite:///{sqlite_path}'
    
    return render_db_url