# точка входа для Flask.

import os
from app import create_app

# Создаём приложение в режиме разработки
app = create_app('development')