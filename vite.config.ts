import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Libraries get their own files so a deploy that only changes app code keeps them cached.
// Firestore is separate from the rest of Firebase so the login page doesn't load it.
function vendorChunk(id: string) {
  if (!id.includes('node_modules')) return
  if (/[\\/](@firebase[\\/](firestore|webchannel-wrapper)|firebase[\\/]firestore)[\\/]/.test(id)) return 'firestore'
  if (/[\\/](@firebase|firebase|idb)[\\/]/.test(id)) return 'firebase'
  if (/[\\/](react|react-dom|react-router|react-router-dom|scheduler|cookie|set-cookie-parser)[\\/]/.test(id)) return 'react'
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: { manualChunks: vendorChunk },
    },
  },
})
