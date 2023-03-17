describe('document-detail', () => {
  beforeEach(() => {
    // also uses global fixtures from cypress/support/e2e.ts

    this.modifiedDocuments = []

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

    cy.fixture('documents/1/notes.json').then((notesJson) => {
      cy.intercept(
        'GET',
        'http://localhost:8000/api/documents/1/notes/',
        (req) => {
          req.reply(notesJson.filter((c) => c.id != 10)) // 3
        }
      )

      cy.intercept(
        'DELETE',
        'http://localhost:8000/api/documents/1/notes/?id=9',
        (req) => {
          req.reply(notesJson.filter((c) => c.id != 9 && c.id != 10)) // 2
        }
      )

      cy.intercept(
        'POST',
        'http://localhost:8000/api/documents/1/notes/',
        (req) => {
          req.reply(notesJson) // 4
        }
      )
    })

    cy.viewport(1024, 1024)
    cy.visit('/documents/1/').wait('@ui-settings')
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

  it('should show a mobile preview', () => {
    cy.viewport(440, 1000)
    cy.get('a')
      .contains('Preview')
      .scrollIntoView({ offset: { top: 150, left: 0 } })
      .click()
    cy.get('pdf-viewer').should('be.visible')
  })

  it('should show a list of notes', () => {
    cy.wait(1000).get('a').contains('Notes').click({ force: true }).wait(1000)
    cy.get('app-document-notes').find('.card').its('length').should('eq', 3)
  })

  it('should support note deletion', () => {
    cy.wait(1000).get('a').contains('Notes').click().wait(1000)
    cy.get('app-document-notes')
      .find('.card')
      .first()
      .find('button')
      .click({ force: true })
      .wait(500)
    cy.get('app-document-notes').find('.card').its('length').should('eq', 2)
  })

  it('should support note insertion', () => {
    cy.wait(1000).get('a').contains('Notes').click().wait(1000)
    cy.get('app-document-notes')
      .find('form textarea')
      .type('Testing new note')
      .wait(500)
    cy.get('app-document-notes').find('form button').click().wait(1500)
    cy.get('app-document-notes').find('.card').its('length').should('eq', 4)
  })

  it('should support navigation to notes tab by url', () => {
    cy.visit('/documents/1/notes')
    cy.get('app-document-notes').should('exist')
  })

  it('should dynamically update note counts', () => {
    cy.visit('/documents/1/notes')
    cy.get('app-document-notes').within(() => cy.contains('Delete').click())
    cy.get('ul.nav').find('li').contains('Notes').find('.badge').contains('2')
  })
})
