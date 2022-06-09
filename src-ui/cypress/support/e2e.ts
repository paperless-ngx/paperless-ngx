// mock API methods

beforeEach(() => {
  cy.intercept('http://localhost:8000/api/ui_settings/', {
    fixture: 'ui_settings/settings.json',
  })

  cy.intercept('http://localhost:8000/api/remote_version/', {
    fixture: 'remote_version/remote_version.json',
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

  cy.intercept('http://localhost:8000/api/storage_paths/*', {
    fixture: 'storage_paths/storage_paths.json',
  })

  cy.intercept('http://localhost:8000/api/documents/1/metadata/', {
    fixture: 'documents/1/metadata.json',
  })

  cy.intercept('http://localhost:8000/api/documents/1/suggestions/', {
    fixture: 'documents/1/suggestions.json',
  })

  cy.intercept('http://localhost:8000/api/documents/1/thumb/', {
    fixture: 'documents/lorem-ipsum.png',
  })
})
