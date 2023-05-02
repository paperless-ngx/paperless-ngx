import { defineConfig } from 'cypress'

export default defineConfig({
  videosFolder: 'cypress/videos',
  video: false,
  screenshotsFolder: 'cypress/screenshots',
  fixturesFolder: 'cypress/fixtures',
  e2e: {
    setupNodeEvents(on, config) {
      return require('./cypress/plugins/index.ts')(on, config)
    },
    baseUrl: 'http://localhost:4200',
  },
})
