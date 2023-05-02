describe('settings', () => {
  beforeEach(() => {
    // also uses global fixtures from cypress/support/e2e.ts

    // mock restricted permissions
    cy.intercept('http://localhost:8000/api/ui_settings/', {
      fixture: 'ui_settings/settings_restricted.json',
    })
  })

  it('should not allow user to edit settings', () => {
    cy.visit('/dashboard')
    cy.contains('Settings').should('not.exist')
    cy.visit('/settings').wait(2000)
    cy.contains("You don't have permissions to do that").should('exist')
  })

  it('should not allow user to view documents', () => {
    cy.visit('/dashboard')
    cy.contains('Documents').should('not.exist')
    cy.visit('/documents').wait(2000)
    cy.contains("You don't have permissions to do that").should('exist')
    cy.visit('/documents/1').wait(2000)
    cy.contains("You don't have permissions to do that").should('exist')
  })

  it('should not allow user to view correspondents', () => {
    cy.visit('/dashboard')
    cy.contains('Correspondents').should('not.exist')
    cy.visit('/correspondents').wait(2000)
    cy.contains("You don't have permissions to do that").should('exist')
  })

  it('should not allow user to view tags', () => {
    cy.visit('/dashboard')
    cy.contains('Tags').should('not.exist')
    cy.visit('/tags').wait(2000)
    cy.contains("You don't have permissions to do that").should('exist')
  })

  it('should not allow user to view document types', () => {
    cy.visit('/dashboard')
    cy.contains('Document Types').should('not.exist')
    cy.visit('/documenttypes').wait(2000)
    cy.contains("You don't have permissions to do that").should('exist')
  })

  it('should not allow user to view storage paths', () => {
    cy.visit('/dashboard')
    cy.contains('Storage Paths').should('not.exist')
    cy.visit('/storagepaths').wait(2000)
    cy.contains("You don't have permissions to do that").should('exist')
  })

  it('should not allow user to view logs', () => {
    cy.visit('/dashboard')
    cy.contains('Logs').should('not.exist')
    cy.visit('/logs').wait(2000)
    cy.contains("You don't have permissions to do that").should('exist')
  })

  it('should not allow user to view tasks', () => {
    cy.visit('/dashboard')
    cy.contains('Tasks').should('not.exist')
    cy.visit('/tasks').wait(2000)
    cy.contains("You don't have permissions to do that").should('exist')
  })
})
