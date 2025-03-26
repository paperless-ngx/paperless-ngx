import { HttpTestingController } from '@angular/common/http/testing'
import { Subscription } from 'rxjs'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { commonAbstractEdocServiceTests } from './abstract-edoc-service.spec'
import { DocumentNotesService } from './document-notes.service'

let httpTestingController: HttpTestingController
let service: DocumentNotesService
let subscription: Subscription
const documentId = 12
const endpoint = 'documents'
const endpoint2 = 'notes'
const notes = [
  {
    created: new Date(),
    note: 'contents 1',
    user: 1,
  },
  {
    created: new Date(),
    note: 'contents 2',
    user: 1,
  },
  {
    created: new Date(),
    note: 'contents 3',
    user: 2,
  },
]

// run common tests
commonAbstractEdocServiceTests(endpoint, DocumentNotesService)

describe(`Additional service tests for DocumentNotesService`, () => {
  test('should call correct api endpoint on get notes', () => {
    subscription = service.getNotes(documentId).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documentId}/${endpoint2}/`
    )
    expect(req.request.method).toEqual('GET')
  })

  test('should call correct api endpoint on add note', () => {
    const content = 'some new text'
    subscription = service.addNote(documentId, content).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documentId}/${endpoint2}/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({
      note: content,
    })
  })

  test('should call correct api endpoint on delete note', () => {
    const noteId = 11
    subscription = service.deleteNote(documentId, noteId).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${documentId}/${endpoint2}/?id=${noteId}`
    )
    expect(req.request.method).toEqual('DELETE')
  })

  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(DocumentNotesService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })
})
