describe('document-detail', () => {
  beforeEach(() => {
    this.modifiedDocuments = []

    cy.intercept('http://localhost:8000/api/frontend_settings/', {
      fixture: 'frontend_settings/settings.json',
    })
    cy.fixture('documents/documents.json').then((documentsJson) => {
      cy.intercept('GET', 'http://localhost:8000/api/documents/1/', (req) => {
        let response = { ...documentsJson }
        response = response.results.find((d) => d.id == 1)
        req.reply(response)
      })
    })

    cy.intercept('PUT', 'http://localhost:8000/api/documents/1/', (req) => {
      this.modifiedDocuments.push(req.body) // store this for later
      req.reply({ result: 'OK' })
    }).as('saveDoc')

    cy.intercept('http://localhost:8000/api/documents/1/metadata/', {
      fixture: 'documents/1/metadata.json',
    })

    cy.intercept('http://localhost:8000/api/documents/1/suggestions/', {
      fixture: 'documents/1/suggestions.json',
    })

    cy.intercept('http://localhost:8000/api/saved_views/*', {
      fixture: 'saved_views/savedviews.json',
    })

    cy.intercept('http://localhost:8000/api/tags/*', {
      fixture: 'tags/tags.json',
    })

    cy.intercept('http://localhost:8000/api/correspondents/*', {
      fixture: 'correspondents/correspondents.json',
    })

    cy.intercept('http://localhost:8000/api/document_types/*', {
      fixture: 'document_types/doctypes.json',
    })

    cy.viewport(1024, 1024)
    cy.visit('/documents/1/')
  })

  it('should activate / deactivate save button when changes are saved', () => {
    cy.contains('button', 'Save').should('be.disabled')
    cy.get('app-input-text[formcontrolname="title"]')
      .type(' additional')
      .wait(1500) // this delay is for frontend debounce
    cy.contains('button', 'Save').should('not.be.disabled')
  })

  it('should warn on unsaved changes', () => {
    cy.get('app-input-text[formcontrolname="title"]')
      .type(' additional')
      .wait(1500) // this delay is for frontend debounce
    cy.get('button[title="Close"]').click()
    cy.contains('You have unsaved changes')
    cy.contains('button', 'Cancel').click().wait(150)
    cy.contains('button', 'Save').click().wait('@saveDoc').wait(2000) // navigates away after saving
    cy.contains('You have unsaved changes').should('not.exist')
  })
})
