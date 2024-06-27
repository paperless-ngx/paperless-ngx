import { TestBed } from '@angular/core/testing'
import { OpenDocumentsService } from './open-documents.service'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'
import { Subscription, throwError } from 'rxjs'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { ConfirmDialogComponent } from '../components/common/confirm-dialog/confirm-dialog.component'
import { OPEN_DOCUMENT_SERVICE } from '../data/storage-keys'
import { wind } from 'ngx-bootstrap-icons'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

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
  {
    id: 4,
    title: 'Doc 4',
    content: 'some content',
  },
  {
    id: 5,
    title: 'Doc 5',
    content: 'some content',
  },
  {
    id: 6,
    title: 'Doc 6',
    content: 'some content',
  },
]

describe('OpenDocumentsService', () => {
  let httpTestingController: HttpTestingController
  let openDocumentsService: OpenDocumentsService
  let modalService: NgbModal
  let subscriptions: Subscription[] = []

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [ConfirmDialogComponent],
      imports: [],
      providers: [
        OpenDocumentsService,
        NgbModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    sessionStorage.clear()
    httpTestingController = TestBed.inject(HttpTestingController)
    openDocumentsService = TestBed.inject(OpenDocumentsService)
    modalService = TestBed.inject(NgbModal)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  afterAll(() => {
    subscriptions?.forEach((subscription) => {
      subscription.unsubscribe()
    })
  })

  it('should open documents', () => {
    subscriptions.push(
      openDocumentsService.openDocument(documents[0]).subscribe()
    )
    expect(openDocumentsService.getOpenDocuments()).toHaveLength(1)
    const doc = openDocumentsService.getOpenDocument(documents[0].id)
    expect(doc.id).toEqual(documents[0].id)
  })

  it('should limit number of open documents', () => {
    subscriptions.push(
      openDocumentsService.openDocument(documents[0]).subscribe()
    )
    subscriptions.push(
      openDocumentsService.openDocument(documents[1]).subscribe()
    )
    subscriptions.push(
      openDocumentsService.openDocument(documents[2]).subscribe()
    )
    subscriptions.push(
      openDocumentsService.openDocument(documents[3]).subscribe()
    )
    subscriptions.push(
      openDocumentsService.openDocument(documents[4]).subscribe()
    )
    subscriptions.push(
      openDocumentsService.openDocument(documents[5]).subscribe()
    )
    expect(openDocumentsService.getOpenDocuments()).toHaveLength(5)
  })

  it('should close documents', () => {
    openDocumentsService.closeDocument({ id: 999 } as any)
    subscriptions.push(
      openDocumentsService.openDocument(documents[0]).subscribe()
    )
    expect(openDocumentsService.getOpenDocuments()).toHaveLength(1)
    openDocumentsService.closeDocument(documents[0])
    expect(openDocumentsService.getOpenDocuments()).toHaveLength(0)
    subscriptions.push(
      openDocumentsService.openDocument(documents[0]).subscribe()
    )
    subscriptions.push(
      openDocumentsService.openDocument(documents[1]).subscribe()
    )
    expect(openDocumentsService.getOpenDocuments()).toHaveLength(2)
    subscriptions.push(openDocumentsService.closeAll().subscribe())
  })

  it('should allow set dirty status, warn on close', () => {
    subscriptions.push(
      openDocumentsService.openDocument(documents[0]).subscribe()
    )
    openDocumentsService.setDirty({ id: 999 }, true) // coverage
    openDocumentsService.setDirty(documents[0], false)
    expect(openDocumentsService.hasDirty()).toBeFalsy()
    openDocumentsService.setDirty(documents[0], true)
    expect(openDocumentsService.hasDirty()).toBeTruthy()
    expect(openDocumentsService.isDirty(documents[0])).toBeTruthy()
    let openModal
    modalService.activeInstances.subscribe((instances) => {
      openModal = instances[0]
    })
    const modalSpy = jest.spyOn(modalService, 'open')
    subscriptions.push(
      openDocumentsService.closeDocument(documents[0]).subscribe()
    )
    expect(modalSpy).toHaveBeenCalled()
    openModal.componentInstance.confirmClicked.next()
  })

  it('should allow set dirty status, warn on closeAll', () => {
    subscriptions.push(
      openDocumentsService.openDocument(documents[0]).subscribe()
    )
    subscriptions.push(
      openDocumentsService.openDocument(documents[1]).subscribe()
    )
    openDocumentsService.setDirty(documents[0], true)
    expect(openDocumentsService.hasDirty()).toBeTruthy()
    let openModal
    modalService.activeInstances.subscribe((instances) => {
      openModal = instances[0]
    })
    const modalSpy = jest.spyOn(modalService, 'open')
    subscriptions.push(openDocumentsService.closeAll().subscribe())
    expect(modalSpy).toHaveBeenCalled()
    openModal.componentInstance.confirmClicked.next()
  })

  it('should load open documents from localStorage', () => {
    sessionStorage.setItem(
      OPEN_DOCUMENT_SERVICE.DOCUMENTS,
      JSON.stringify(documents)
    )
    const testOpenDocumentsService = new OpenDocumentsService(
      null,
      modalService
    )
    expect(testOpenDocumentsService.getOpenDocuments()).toHaveLength(
      documents.length
    )
  })

  it('should remove open documents from localStorage on error', () => {
    sessionStorage.setItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS, 'hello world')
    const testOpenDocumentsService = new OpenDocumentsService(
      null,
      modalService
    )
    expect(testOpenDocumentsService.getOpenDocuments()).toHaveLength(0)
    expect(sessionStorage.getItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS)).toBeNull()
  })

  it('should save open documents to localStorage', () => {
    subscriptions.push(
      openDocumentsService.openDocument(documents[0]).subscribe()
    )
    subscriptions.push(
      openDocumentsService.openDocument(documents[1]).subscribe()
    )
    subscriptions.push(
      openDocumentsService.openDocument(documents[2]).subscribe()
    )
    openDocumentsService.save()
    const localStorageDocs = JSON.parse(
      sessionStorage.getItem(OPEN_DOCUMENT_SERVICE.DOCUMENTS)
    )
    expect(localStorageDocs).toContainEqual(documents[0])
    expect(localStorageDocs).toContainEqual(documents[1])
    expect(localStorageDocs).toContainEqual(documents[2])
  })

  it('should refresh documents', () => {
    subscriptions.push(
      openDocumentsService.openDocument(documents[1]).subscribe()
    )
    openDocumentsService.refreshDocument(documents[1].id)
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/${documents[1].id}/?full_perms=true`
    )
    expect(req.request.method).toEqual('GET')
    req.flush(documents[1])
    expect(openDocumentsService.getOpenDocuments()).toHaveLength(1)
  })

  it('should handle error on refresh documents', () => {
    subscriptions.push(
      openDocumentsService.openDocument(documents[1]).subscribe()
    )
    openDocumentsService.refreshDocument(documents[1].id)
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/${documents[1].id}/?full_perms=true`
    )
    expect(req.request.method).toEqual('GET')
    req.error(new ErrorEvent('timeout'))
    expect(openDocumentsService.getOpenDocuments()).toHaveLength(0)
  })

  it('should log error on sessionStorage save', () => {
    const doc = { ...documents[0] }
    doc.content = 'a'.repeat(1000000)
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation()
    openDocumentsService.openDocument(doc)
    expect(consoleSpy).toHaveBeenCalled()
  })
})
