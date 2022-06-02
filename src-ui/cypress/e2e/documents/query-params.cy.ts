import { PaperlessDocument } from 'src/app/data/paperless-document'

describe('documents query params', () => {
  beforeEach(() => {
    // also uses global fixtures from cypress/support/e2e.ts

    cy.fixture('documents/documents.json').then((documentsJson) => {
      // mock api filtering
      cy.intercept('GET', 'http://localhost:8000/api/documents/*', (req) => {
        let response = { ...documentsJson }

        if (req.query.hasOwnProperty('ordering')) {
          const sort_field = req.query['ordering'].toString().replace('-', '')
          const reverse = req.query['ordering'].toString().indexOf('-') !== -1
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).sort((docA, docB) => {
            let result = 0
            switch (sort_field) {
              case 'created':
              case 'added':
                result =
                  new Date(docA[sort_field]) < new Date(docB[sort_field])
                    ? -1
                    : 1
                break
              case 'archive_serial_number':
                result = docA[sort_field] < docB[sort_field] ? -1 : 1
                break
            }
            if (reverse) result = -result
            return result
          })
        }

        if (req.query.hasOwnProperty('tags__id__in')) {
          const tag_ids: Array<number> = req.query['tags__id__in']
            .toString()
            .split(',')
            .map((v) => +v)
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter(
            (d) =>
              d.tags.length > 0 &&
              d.tags.filter((t) => tag_ids.includes(t)).length > 0
          )
          response.count = response.results.length
        } else if (req.query.hasOwnProperty('tags__id__none')) {
          const tag_ids: Array<number> = req.query['tags__id__none']
            .toString()
            .split(',')
            .map((v) => +v)
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => d.tags.filter((t) => tag_ids.includes(t)).length == 0)
          response.count = response.results.length
        } else if (
          req.query.hasOwnProperty('is_tagged') &&
          req.query['is_tagged'] == '0'
        ) {
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => d.tags.length == 0)
          response.count = response.results.length
        }

        if (req.query.hasOwnProperty('document_type__id')) {
          const doctype_id = +req.query['document_type__id']
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => d.document_type == doctype_id)
          response.count = response.results.length
        } else if (
          req.query.hasOwnProperty('document_type__isnull') &&
          req.query['document_type__isnull'] == '1'
        ) {
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => d.document_type == undefined)
          response.count = response.results.length
        }

        if (req.query.hasOwnProperty('correspondent__id')) {
          const correspondent_id = +req.query['correspondent__id']
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => d.correspondent == correspondent_id)
          response.count = response.results.length
        } else if (
          req.query.hasOwnProperty('correspondent__isnull') &&
          req.query['correspondent__isnull'] == '1'
        ) {
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => d.correspondent == undefined)
          response.count = response.results.length
        }

        if (req.query.hasOwnProperty('storage_path__id')) {
          const storage_path_id = +req.query['storage_path__id']
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => d.storage_path == storage_path_id)
          response.count = response.results.length
        } else if (
          req.query.hasOwnProperty('storage_path__isnull') &&
          req.query['storage_path__isnull'] == '1'
        ) {
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => d.storage_path == undefined)
          response.count = response.results.length
        }

        if (req.query.hasOwnProperty('created__date__gt')) {
          const date = new Date(req.query['created__date__gt'])
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => new Date(d.created) > date)
          response.count = response.results.length
        } else if (req.query.hasOwnProperty('created__date__lt')) {
          const date = new Date(req.query['created__date__lt'])
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => new Date(d.created) < date)
          response.count = response.results.length
        }

        if (req.query.hasOwnProperty('added__date__gt')) {
          const date = new Date(req.query['added__date__gt'])
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => new Date(d.added) > date)
          response.count = response.results.length
        } else if (req.query.hasOwnProperty('added__date__lt')) {
          const date = new Date(req.query['added__date__lt'])
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => new Date(d.added) < date)
          response.count = response.results.length
        }

        if (req.query.hasOwnProperty('title_content')) {
          const title_content_regexp = new RegExp(
            req.query['title_content'].toString(),
            'i'
          )
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter(
            (d) =>
              title_content_regexp.test(d.title) ||
              title_content_regexp.test(d.content)
          )
          response.count = response.results.length
        }

        if (req.query.hasOwnProperty('archive_serial_number')) {
          const asn = +req.query['archive_serial_number']
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) => d.archive_serial_number == asn)
          response.count = response.results.length
        } else if (req.query.hasOwnProperty('archive_serial_number__isnull')) {
          const isnull = req.query['storage_path__isnull'] == '1'
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter((d) =>
            isnull
              ? d.archive_serial_number == undefined
              : d.archive_serial_number != undefined
          )
          response.count = response.results.length
        } else if (req.query.hasOwnProperty('archive_serial_number__gt')) {
          const asn = +req.query['archive_serial_number__gt']
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter(
            (d) => d.archive_serial_number > 0 && d.archive_serial_number > asn
          )
          response.count = response.results.length
        } else if (req.query.hasOwnProperty('archive_serial_number__lt')) {
          const asn = +req.query['archive_serial_number__lt']
          response.results = (
            documentsJson.results as Array<PaperlessDocument>
          ).filter(
            (d) => d.archive_serial_number > 0 && d.archive_serial_number < asn
          )
          response.count = response.results.length
        }

        req.reply(response)
      })
    })
  })

  it('should show a list of documents sorted by created', () => {
    cy.visit('/documents?sort=created')
    cy.get('app-document-card-small').first().contains('No latin title')
  })

  it('should show a list of documents reverse sorted by created', () => {
    cy.visit('/documents?sort=created&reverse=true')
    cy.get('app-document-card-small').first().contains('sit amet')
  })

  it('should show a list of documents sorted by added', () => {
    cy.visit('/documents?sort=added')
    cy.get('app-document-card-small').first().contains('No latin title')
  })

  it('should show a list of documents reverse sorted by added', () => {
    cy.visit('/documents?sort=added&reverse=true')
    cy.get('app-document-card-small').first().contains('sit amet')
  })

  it('should show a list of documents filtered by any tags', () => {
    cy.visit('/documents?sort=created&reverse=true&tags__id__in=2,4,5')
    cy.contains('3 documents')
  })

  it('should show a list of documents filtered by excluded tags', () => {
    cy.visit('/documents?sort=created&reverse=true&tags__id__none=2,4')
    cy.contains('One document')
  })

  it('should show a list of documents filtered by no tags', () => {
    cy.visit('/documents?sort=created&reverse=true&is_tagged=0')
    cy.contains('One document')
  })

  it('should show a list of documents filtered by document type', () => {
    cy.visit('/documents?sort=created&reverse=true&document_type__id=1')
    cy.contains('3 documents')
  })

  it('should show a list of documents filtered by no document type', () => {
    cy.visit('/documents?sort=created&reverse=true&document_type__isnull=1')
    cy.contains('One document')
  })

  it('should show a list of documents filtered by correspondent', () => {
    cy.visit('/documents?sort=created&reverse=true&correspondent__id=9')
    cy.contains('2 documents')
  })

  it('should show a list of documents filtered by no correspondent', () => {
    cy.visit('/documents?sort=created&reverse=true&correspondent__isnull=1')
    cy.contains('2 documents')
  })

  it('should show a list of documents filtered by storage path', () => {
    cy.visit('/documents?sort=created&reverse=true&storage_path__id=2')
    cy.contains('One document')
  })

  it('should show a list of documents filtered by no storage path', () => {
    cy.visit('/documents?sort=created&reverse=true&storage_path__isnull=1')
    cy.contains('3 documents')
  })

  it('should show a list of documents filtered by title or content', () => {
    cy.visit('/documents?sort=created&reverse=true&title_content=lorem')
    cy.contains('2 documents')
  })

  it('should show a list of documents filtered by asn', () => {
    cy.visit('/documents?sort=created&reverse=true&archive_serial_number=12345')
    cy.contains('One document')
  })

  it('should show a list of documents filtered by empty asn', () => {
    cy.visit(
      '/documents?sort=created&reverse=true&archive_serial_number__isnull=1'
    )
    cy.contains('2 documents')
  })

  it('should show a list of documents filtered by non-empty asn', () => {
    cy.visit(
      '/documents?sort=created&reverse=true&archive_serial_number__isnull=0'
    )
    cy.contains('2 documents')
  })

  it('should show a list of documents filtered by asn greater than', () => {
    cy.visit(
      '/documents?sort=created&reverse=true&archive_serial_number__gt=12346'
    )
    cy.contains('One document')
  })

  it('should show a list of documents filtered by asn less than', () => {
    cy.visit(
      '/documents?sort=created&reverse=true&archive_serial_number__lt=12346'
    )
    cy.contains('One document')
  })

  it('should show a list of documents filtered by created date greater than', () => {
    cy.visit(
      '/documents?sort=created&reverse=true&created__date__gt=2022-03-23'
    )
    cy.contains('3 documents')
  })

  it('should show a list of documents filtered by created date less than', () => {
    cy.visit(
      '/documents?sort=created&reverse=true&created__date__lt=2022-03-23'
    )
    cy.contains('One document')
  })

  it('should show a list of documents filtered by added date greater than', () => {
    cy.visit('/documents?sort=created&reverse=true&added__date__gt=2022-03-24')
    cy.contains('2 documents')
  })

  it('should show a list of documents filtered by added date less than', () => {
    cy.visit('/documents?sort=created&reverse=true&added__date__lt=2022-03-24')
    cy.contains('2 documents')
  })

  it('should show a list of documents filtered by multiple filters', () => {
    cy.visit(
      '/documents?sort=created&reverse=true&document_type__id=1&correspondent__id=9&tags__id__in=4,5'
    )
    cy.contains('2 documents')
  })
})
