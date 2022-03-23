describe('documents-list', () => {
  beforeEach(() => {
    cy.intercept('http://localhost:8000/api/documents/*', {
      fixture: 'documents/documents.json',
    });
    cy.intercept('http://localhost:8000/api/documents/1/thumb/', {
      fixture: 'documents/lorem-ipsum.png',
    });

    cy.visit('/documents');
  });

  it('should show a list of documents rendered as cards with thumbnails', () => {
    cy.contains('One document');
    cy.contains('lorem-ipsum');
    cy.get('app-document-card-small:first-of-type img')
      .invoke('attr', 'src')
      .should('eq', 'http://localhost:8000/api/documents/1/thumb/');
  });
});
