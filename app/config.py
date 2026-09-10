from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_USER : str = "cricuser"
    DB_PASSWORD : str = "cricpass"
    DB_HOST : str = "cricbuzz-db"
    DB_PORT : str = "5432"
    DB_NAME : str = "cricbuzz"
    
settings = Settings()