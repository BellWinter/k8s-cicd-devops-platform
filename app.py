from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def hello():
    version = os.getenv('APP_VERSION', 'v1.0')
    return f'''
    <html>
    <head><title>K8s CI/CD Demo v3.0</title></head>
    <body style="font-family: Arial; text-align: center; margin-top: 100px;">
        <h1>云原生 CI/CD Demo v3.0 应用</h1>
        <p>版本: {version}</p>
        <p>部署方式: Jenkins Pipeline + Kubernetes</p>
        <p>状态: 运行中</p>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    return {'status': 'healthy', 'version': os.getenv('APP_VERSION', 'v1.0')}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
