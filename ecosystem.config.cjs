const path = require('path')

const root = __dirname

module.exports = {
  apps: [
    {
      name: 'oppora-backend',
      cwd: root,
      script: path.join(root, '.venv', 'bin', 'python'),
      args: '-m uvicorn backend.main:app --host 127.0.0.1 --port 8000',
      env: {
        PYTHONPATH: root,
      },
      autorestart: true,
      max_restarts: 10,
    },
    {
      name: 'oppora-frontend',
      cwd: path.join(root, 'frontend'),
      script: 'npm',
      args: 'run start -- --hostname 127.0.0.1 --port 3000',
      env: {
        NODE_ENV: 'production',
      },
      autorestart: true,
      max_restarts: 10,
    },
  ],
}
