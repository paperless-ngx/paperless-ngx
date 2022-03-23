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
    cy.contains('3 documents')
    cy.contains('lorem-ipsum')
    cy.get('app-document-card-small:first-of-type img')
      .invoke('attr', 'src')
      .should('eq', 'http://localhost:8000/api/documents/1/thumb/')
  })

  it('should change to table "details" view', () => {
    cy.get('div.btn-group-toggle input[value="details"]').parent().click()
    cy.get('table')
  })

  it('should change to large cards view', () => {
    cy.get('div.btn-group-toggle input[value="largeCards"]').parent().click()
    cy.get('app-document-card-large')
  })

  it('should filter tags', () => {
    // e.g. http://localhost:8000/api/documents/?page=1&page_size=50&ordering=-created&tags__id__all=2
    cy.intercept('http://localhost:8000/api/documents/*', {
      fixture: 'documents/documents_filtered.json',
    })
    cy.get('app-filter-editor app-filterable-dropdown[title="Tags"]').within(
      () => {
        cy.contains('button', 'Tags').click()
        cy.contains('button', 'Tag 2').click()
      }
    )
    cy.contains('One document')
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
