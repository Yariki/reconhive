import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createVuetify } from 'vuetify'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'

import App from './App.vue'
import router from './router'

const vuetify = createVuetify({
  theme: {
    defaultTheme: 'reconhiveDark',
    themes: {
      reconhiveDark: {
        dark: true,
        colors: {
          background: '#0d1117',
          surface: '#161b22',
          primary: '#2f81f7',
          secondary: '#7ee787',
          error: '#f85149',
          warning: '#d29922',
          success: '#3fb950',
        },
      },
    },
  },
})

createApp(App).use(createPinia()).use(router).use(vuetify).mount('#app')
