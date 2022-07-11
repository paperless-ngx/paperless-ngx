describe('documents-list', () => {
  beforeEach(() => {
    // also uses global fixtures from cypress/support/e2e.ts

    this.bulkEdits = {}

    cy.fixture('documents/documents.json').then((documentsJson) => {
      // bulk edit
      cy.intercept(
        'POST',
        'http://localhost:8000/api/documents/bulk_edit/',
        (req) => {
          this.bulkEdits = req.body // store this for later
          req.reply({ result: 'OK' })
        }
      )

      cy.intercept('GET', 'http://localhost:8000/api/documents/*', (req) => {
        let response = { ...documentsJson }

        // bulkEdits was set earlier by bulk_edit intercept
        if (this.bulkEdits.hasOwnProperty('documents')) {
          response.results = response.results.map((d) => {
            if ((this.bulkEdits['documents'] as Array<number>).includes(d.id)) {
              switch (this.bulkEdits['method']) {
                case 'modify_tags':
                  d.tags = (d.tags as Array<number>).concat([
                    this.bulkEdits['parameters']['add_tags'],
                  ])
                  break
                case 'set_correspondent':
                  d.correspondent =
                    this.bulkEdits['parameters']['correspondent']
                  break
                case 'set_document_type':
                  d.document_type =
                    this.bulkEdits['parameters']['document_type']
                  break
              }
            }

            return d
          })
        } else if (req.query.hasOwnProperty('tags__id__all')) {
          // filtering e.g. http://localhost:8000/api/documents/?page=1&page_size=50&ordering=-created&tags__id__all=2
          const tag_id = +req.query['tags__id__all']
          response.results = (documentsJson.results as Array<any>).filter((d) =>
            (d.tags as Array<number>).includes(tag_id)
          )
          response.count = response.results.length
        }

        req.reply(response)
      })
    })

    cy.viewport(1280, 1024)
    cy.visit('/documents')
  })

  it('should show a list of documents rendered as cards with thumbnails', () => {
    cy.contains('3 documents')
    cy.contains('lorem ipsum')
    cy.get('app-document-card-small:first-of-type img')
      .invoke('attr', 'src')
      .should('eq', 'http://localhost:8000/api/documents/1/thumb/')
  })

  it('should change to table "details" view', () => {
    cy.get('div.btn-group input[value="details"]').next().click()
    cy.get('table')
  })

  it('should change to large cards view', () => {
    cy.get('div.btn-group input[value="largeCards"]').next().click()
    cy.get('app-document-card-large')
  })

  it('should filter tags', () => {
    cy.get('app-filter-editor app-filterable-dropdown[title="Tags"]').within(
      () => {
        cy.contains('button', 'Tags').click()
        cy.contains('button', 'Tag 2').click()
      }
    )
    cy.contains('One document')
  })

  it('should apply tags', () => {
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
