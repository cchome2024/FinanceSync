module.exports = {
  apps: [
    {
      name: 'financesync-backend',
      script: '/opt/FinanceSync/backend/start_server_pm2.sh',
      cwd: '/opt/FinanceSync/backend',
      interpreter: 'bash',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
      },
      error_file: '/opt/FinanceSync/logs/backend-error.log',
      out_file: '/opt/FinanceSync/logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
    },
  ],
}

