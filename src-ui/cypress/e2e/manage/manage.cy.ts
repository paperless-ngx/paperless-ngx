describe('manage', () => {
  // also uses global fixtures from cypress/support/e2e.ts

  it('should show a list of correspondents with bottom pagination as well', () => {
    cy.visit('/correspondents')
    cy.get('tbody').find('tr').its('length').should('eq', 25)
    cy.get('ngb-pagination').its('length').should('eq', 2)
  })

  it('should show a list of tags without bottom pagination', () => {
    cy.visit('/tags')
    cy.get('tbody').find('tr').its('length').should('eq', 8)
    cy.get('ngb-pagination').its('length').should('eq', 1)
  })

  it('should show a list of documents filtered by tag', () => {
    cy.intercept('http://localhost:8000/api/documents/*', (req) => {
      if (req.url.indexOf('tags__id__all=4'))
        req.reply({ count: 3, next: null, previous: null, results: [] })
    })
    cy.visit('/tags')
    cy.get('tbody').find('button:visible').contains('Documents').first().click() // id = 4
    cy.contains('3 documents')
  })
})
