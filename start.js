import { serve } from '@hono/node-server';
import app from './dist/index.js';

console.log('🚀 Server starting on http://127.0.0.1:8787');
console.log('📍 Press Ctrl+C to stop');

serve({
  fetch: app.fetch,
  port: 8787,
  hostname: '0.0.0.0'
}, (info) => {
  console.log(`✅ Server running on http://127.0.0.1:${info.port}`);
});