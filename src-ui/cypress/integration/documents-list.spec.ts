describe('documents-list', () => {
  beforeEach(() => {
    cy.intercept('http://localhost:8000/api/documents/*', {
      fixture: 'documents/documents.json',
    })
    cy.intercept('http://localhost:8000/api/documents/1/thumb/', {
      fixture: 'documents/lorem-ipsum.png',
    })
    cy.intercept('http://localhost:8000/api/tags/*', {
      fixture: 'documents/tags.json',
    })
    cy.intercept('http://localhost:8000/api/correspondents/*', {
      fixture: 'documents/correspondents.json',
    })
    cy.intercept('http://localhost:8000/api/document_types/*', {
      fixture: 'documents/doctypes.json',
    })

    cy.visit('/documents')
  })

  it('should show a list of documents rendered as cards with thumbnails', () => {
    cy.contains('One document')
    cy.contains('lorem-ipsum')
    cy.get('app-document-card-small:first-of-type img')
      .invoke('attr', 'src')
      .should('eq', 'http://localhost:8000/api/documents/1/thumb/')
  })

  it('should apply tags', () => {
    cy.intercept('http://localhost:8000/api/documents/*', {
      fixture: 'documents/documents_saved.json',
    })
    cy.get('app-document-card-small:first-of-type').click()
    cy.get('app-bulk-editor app-filterable-dropdown[title="Tags"]').within(
      () => {
        cy.contains('button', 'Tags').click()
        cy.contains('button', 'Test Tag').click()
        cy.contains('button', 'Apply').click()
      }
    )
    cy.contains('button', 'Confirm').click()
    cy.get('app-document-card-small:first-of-type').contains('Test Tag')
  })

  it('should apply correspondent', () => {
    cy.intercept('http://localhost:8000/api/documents/*', {
      fixture: 'documents/documents_saved.json',
    })
    cy.get('app-document-card-small:first-of-type').click()
    cy.get(
      'app-bulk-editor app-filterable-dropdown[title="Correspondent"]'
    ).within(() => {
      cy.contains('button', 'Correspondent').click()
      cy.contains('button', 'ABC Test Correspondent').click()
      cy.contains('button', 'Apply').click()
    })
    cy.contains('button', 'Confirm').click()
    cy.get('app-document-card-small:first-of-type').contains(
      'ABC Test Correspondent'
    )
  })

  it('should apply document type', () => {
    cy.intercept('http://localhost:8000/api/documents/*', {
      fixture: 'documents/documents_saved.json',
    })
    cy.get('app-document-card-small:first-of-type').click()
    cy.get(
      'app-bulk-editor app-filterable-dropdown[title="Document type"]'
    ).within(() => {
      cy.contains('button', 'Document type').click()
      cy.contains('button', 'Test Doc Type').click()
      cy.contains('button', 'Apply').click()
    })
    cy.contains('button', 'Confirm').click()
    cy.get('app-document-card-small:first-of-type').contains('Test Doc Type')
  })
})
