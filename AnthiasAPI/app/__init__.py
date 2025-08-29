from flask import Flask

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a strong key for production!
