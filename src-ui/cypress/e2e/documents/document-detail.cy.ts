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

    cy.fixture('documents/1/comments.json').then((commentsJson) => {
      cy.intercept(
        'GET',
        'http://localhost:8000/api/documents/1/comments/',
        (req) => {
          req.reply(commentsJson.filter((c) => c.id != 10)) // 3
        }
      )

      cy.intercept(
        'DELETE',
        'http://localhost:8000/api/documents/1/comments/?id=9',
        (req) => {
          req.reply(commentsJson.filter((c) => c.id != 9 && c.id != 10)) // 2
        }
      )

      cy.intercept(
        'POST',
        'http://localhost:8000/api/documents/1/comments/',
        (req) => {
          req.reply(commentsJson) // 4
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

  it('should show a list of comments', () => {
    cy.wait(1000)
      .get('a')
      .contains('Comments')
      .click({ force: true })
      .wait(1000)
    cy.get('app-document-comments').find('.card').its('length').should('eq', 3)
  })

  it('should support comment deletion', () => {
    cy.wait(1000).get('a').contains('Comments').click().wait(1000)
    cy.get('app-document-comments')
      .find('.card')
      .first()
      .find('button')
      .click({ force: true })
      .wait(500)
    cy.get('app-document-comments').find('.card').its('length').should('eq', 2)
  })

  it('should support comment insertion', () => {
    cy.wait(1000).get('a').contains('Comments').click().wait(1000)
    cy.get('app-document-comments')
      .find('form textarea')
      .type('Testing new comment')
      .wait(500)
    cy.get('app-document-comments').find('form button').click().wait(1500)
    cy.get('app-document-comments').find('.card').its('length').should('eq', 4)
  })

  it('should support navigation to comments tab by url', () => {
    cy.visit('/documents/1/comments')
    cy.get('app-document-comments').should('exist')
  })

  it('should dynamically update comment counts', () => {
    cy.visit('/documents/1/comments')
    cy.get('app-document-comments').within(() => cy.contains('Delete').click())
    cy.get('ul.nav')
      .find('li')
      .contains('Comments')
      .find('.badge')
      .contains('2')
  })
})
