import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { Subscription } from 'rxjs'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { DocumentService } from './document.service'
import { FILTER_TITLE } from 'src/app/data/filter-rule-type'
import { SettingsService } from '../settings.service'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import {
  DOCUMENT_SORT_FIELDS,
  DOCUMENT_SORT_FIELDS_FULLTEXT,
} from 'src/app/data/document'
import { PermissionsService } from '../permissions.service'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

let httpTestingController: HttpTestingController
let service: DocumentService
let subscription: Subscription
let settingsService: SettingsService

const endpoint = 'documents'
const documents = [
  {
    id: 1,
    title: 'Doc 1',
    content: 'some content',
    tags: [1, 2, 3],
    correspondent: 11,
    document_type: 3,
    storage_path: 8,
  },
  {
    id: 2,
    title: 'Doc 2',
    content: 'some content',
  },
  {
    id: 3,
    title: 'Doc 3',
    content: 'some content',
  },
]

beforeEach(() => {
  TestBed.configureTestingModule({
    imports: [],
    providers: [
      DocumentService,
      provideHttpClient(withInterceptorsFromDi()),
      provideHttpClientTesting(),
    ],
  })

  httpTestingController = TestBed.inject(HttpTestingController)
  service = TestBed.inject(DocumentService)
  settingsService = TestBed.inject(SettingsService)
})

describe(`DocumentService`, () => {
  // common tests e.g. commonAbstractPaperlessServiceTests differ slightly
  it('should call appropriate api endpoint for list all', () => {
    subscription = service.listAll().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should call appropriate api endpoint for get a single document', () => {
    subscription = service.get(documents[0].id).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/?full_perms=true`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should call appropriate api endpoint for create a single document', () => {
    subscription = service.create(documents[0]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/`
    )
    expect(req.request.method).toEqual('POST')
  })

  it('should call appropriate api endpoint for delete a single document', () => {
    subscription = service.delete(documents[0]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/`
    )
    expect(req.request.method).toEqual('DELETE')
  })

  it('should call appropriate api endpoint for update a single document', () => {
    subscription = service.update(documents[0]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/`
    )
    expect(req.request.method).toEqual('PUT')
  })

  it('should call appropriate api endpoint for patch a single document', () => {
    subscription = service.patch(documents[0]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/`
    )
    expect(req.request.method).toEqual('PATCH')
  })

  it('should call appropriate api endpoint for listing all documents ids in a filter set', () => {
    subscription = service
      .listAllFilteredIds([
        {
          rule_type: FILTER_TITLE,
          value: 'apple',
        },
      ])
      .subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000&fields=id&title__icontains=apple`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should call appropriate api endpoint for uploading a document', () => {
    subscription = service.uploadDocument(documents[0]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/post_document/`
    )
    expect(req.request.method).toEqual('POST')
  })

  it('should call appropriate api endpoint for getting metadata', () => {
    subscription = service.getMetadata(documents[0].id).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/metadata/`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should call appropriate api endpoint for getting selection data', () => {
    const ids = [documents[0].id]
    subscription = service.getSelectionData(ids).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/selection_data/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({
      documents: ids,
    })
  })

  it('should call appropriate api endpoint for getting suggestions', () => {
    subscription = service.getSuggestions(documents[0].id).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/suggestions/`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should call appropriate api endpoint for bulk download', () => {
    const ids = [1, 2, 3]
    const content = 'both'
    const useFilenameFormatting = false
    subscription = service
      .bulkDownload(ids, content, useFilenameFormatting)
      .subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/bulk_download/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({
      documents: ids,
      content,
      follow_formatting: useFilenameFormatting,
    })
  })

  it('should call appropriate api endpoint for bulk edit', () => {
    const ids = [1, 2, 3]
    const method = 'modify_tags'
    const parameters = {
      add_tags: [15],
      remove_tags: [6],
    }
    subscription = service.bulkEdit(ids, method, parameters).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/bulk_edit/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({
      documents: ids,
      method,
      parameters,
    })
  })

  it('should return the correct preview URL for a single document', () => {
    let url = service.getPreviewUrl(documents[0].id)
    expect(url).toEqual(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/preview/`
    )
    url = service.getPreviewUrl(documents[0].id, true)
    expect(url).toEqual(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/preview/?original=true`
    )
  })

  it('should return the correct thumb URL for a single document', () => {
    let url = service.getThumbUrl(documents[0].id)
    expect(url).toEqual(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/thumb/`
    )
  })

  it('should return the correct download URL for a single document', () => {
    let url = service.getDownloadUrl(documents[0].id)
    expect(url).toEqual(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/download/`
    )
    url = service.getDownloadUrl(documents[0].id, true)
    expect(url).toEqual(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/download/?original=true`
    )
  })

  it('should add observables to document', () => {
    subscription = service
      .listFiltered(1, 25, 'title', false, [])
      .subscribe((result) => {
        expect(result.results).toHaveLength(3)
        const doc = result.results[0]
        expect(doc.correspondent$).not.toBeNull()
        expect(doc.document_type$).not.toBeNull()
        expect(doc.tags$).not.toBeNull()
        expect(doc.storage_path$).not.toBeNull()
      })
    httpTestingController
      .expectOne(
        `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=25&ordering=title`
      )
      .flush({
        results: documents,
      })
  })

  it('should set search query', () => {
    const searchQuery = 'hello'
    service.searchQuery = searchQuery
    let url = service.getPreviewUrl(documents[0].id)
    expect(url).toEqual(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/preview/#search="${searchQuery}"`
    )
  })

  it('should support get next asn', () => {
    subscription = service.getNextAsn().subscribe((asn) => asn)
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/next_asn/`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should pass remove_inbox_tags setting to update', () => {
    subscription = service.update(documents[0]).subscribe()
    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/`
    )
    expect(req.request.body.remove_inbox_tags).toEqual(false)

    settingsService.set(SETTINGS_KEYS.DOCUMENT_EDITING_REMOVE_INBOX_TAGS, true)
    subscription = service.update(documents[0]).subscribe()
    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/`
    )
    expect(req.request.body.remove_inbox_tags).toEqual(true)
  })

  it('should call appropriate api endpoint for getting audit log', () => {
    subscription = service.getHistory(documents[0].id).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documents[0].id}/history/`
    )
  })
})

it('should construct sort fields respecting permissions', () => {
  expect(
    service.sortFields.find((f) => f.field === 'correspondent__name')
  ).toBeUndefined()
  expect(
    service.sortFields.find((f) => f.field === 'document_type__name')
  ).toBeUndefined()

  const permissionsService: PermissionsService =
    TestBed.inject(PermissionsService)
  jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(true)
  service['setupSortFields']()
  expect(service.sortFields).toEqual(DOCUMENT_SORT_FIELDS)
  expect(service.sortFieldsFullText).toEqual([
    ...DOCUMENT_SORT_FIELDS,
    ...DOCUMENT_SORT_FIELDS_FULLTEXT,
  ])

  settingsService.set(SETTINGS_KEYS.NOTES_ENABLED, false)
  service['setupSortFields']()
  expect(
    service.sortFields.find((f) => f.field === 'num_notes')
  ).toBeUndefined()
})

afterEach(() => {
  subscription?.unsubscribe()
  httpTestingController.verify()
})
