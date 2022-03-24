describe('settings', () => {
  beforeEach(() => {
    this.modifiedViews = []

    // mock API methods
    cy.fixture('settings/savedviews.json').then((savedViewsJson) => {
      // saved views PATCH
      cy.intercept(
        'PATCH',
        'http://localhost:8000/api/saved_views/*',
        (req) => {
          this.modifiedViews.push(req.body) // store this for later
          req.reply({ result: 'OK' })
        }
      )

      cy.intercept('GET', 'http://localhost:8000/api/saved_views/*', (req) => {
        let response = { ...savedViewsJson }
        if (this.modifiedViews.length) {
          response.results = response.results.map((v) => {
            if (this.modifiedViews.find((mv) => mv.id == v.id))
              v = this.modifiedViews.find((mv) => mv.id == v.id)
            return v
          })
        }

        req.reply(response)
      })
    })

    cy.viewport(1024, 1024)
    cy.visit('/settings')
  })

  it('should activate / deactivate save button when settings change and are saved', () => {
    cy.contains('button', 'Save').should('be.disabled')
    cy.contains('Use system settings').click()
    cy.contains('button', 'Save').should('not.be.disabled')
    cy.contains('button', 'Save').click()
    cy.contains('button', 'Save').should('be.disabled')
  })

  it('should warn on unsaved changes', () => {
    cy.contains('Use system settings').click()
    cy.contains('a', 'Dashboard').click()
    cy.contains('You have unsaved changes')
    cy.contains('button', 'Cancel').click()
    cy.contains('button', 'Save').click()
    cy.visit('/dashboard')
    cy.contains('You have unsaved changes').should('not.exist')
  })

  it('should apply appearance changes when set', () => {
    cy.contains('Use system settings').click()
    cy.get('body').should('not.have.class', 'color-scheme-system')
    cy.contains('Enable dark mode').click()
    cy.get('body').should('have.class', 'color-scheme-dark')
  })

  it('should remove saved view from sidebar when unset', () => {
    cy.contains('a', 'Saved views').click()
    cy.get('#show_in_sidebar_1').click()
    cy.contains('button', 'Save').click()
    cy.contains('li', 'Inbox').should('not.exist')
  })

  it('should remove saved view from dashboard when unset', () => {
    cy.contains('a', 'Saved views').click()
    cy.get('#show_on_dashboard_1').click()
    cy.contains('button', 'Save').click()
    cy.visit('/dashboard')
    cy.get('app-saved-view-widget').contains('Inbox').should('not.exist')
  })
})
